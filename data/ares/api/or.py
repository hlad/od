# TODO: bacha, u angazovanych osob jsou ministerstva bez uvedenych ICO (spousta radek to tak ma - filtruj ale jen ty, co maj jako stat cesko)
# 
# TODO: dodelat angazovane osoby! (dodelano?) mame 29 mapovani - mame 29 distinct typu? select nazev_ang, count(*) from od.ares_or_angos_fo group by 1;
# TODO: CIN, OSK (cinnosti, ostatni skutecnosti), KAP (kapital), REG/SZ (kym zapsano)

import json

import lxml.etree
import psycopg2
import psycopg2.extras
from tqdm import tqdm

def get_el(root, address, namespace):
    el = root.find(address, namespaces=namespace)
    if el is None:
        return el
    return el.text

def get_el_all(root, address, namespace):
    el = root.findall(address, namespaces=namespace)
    if el is None:
        return el
    return [j.text for j in el]

def get_els(root, mapping, namespace):
    ret = {}
    for k, v in mapping.items():
        if isinstance(v, str):
            ret[k] = get_el(root, v, namespace)
        else:
            ret[k] = get_els(root, v, namespace)
    return ret

def get_ico(conn):
    with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute('select ico, xml from od.ares_raw where rejstrik = \'or\' and "xml" is not null and found is true')
        yield from cursor.fetchall()

conn = psycopg2.connect(host='localhost') # TODO: close

for row in tqdm(get_ico(conn)):
    et = lxml.etree.fromstring(row['xml'].tobytes())

    vyp = et.find('./are:Odpoved/D:Vypis_OR', namespaces=et.nsmap)

    udmap = {
        'aktualizace_db': './D:UVOD/D:ADB',
        'datum_vypisu': './D:UVOD/D:DVY',
        'platnost_od': './D:ZAU/D:POD',
        # 'ico': './D:ZAU/D:ICO', # nakonec pouzivame ICO z dotazu
        'datum_zapisu': './D:ZAU/D:DZOR',
        'stav_subjektu': './D:ZAU/D:S/D:SSU', # TODO: ZAU/S veci: konkurzy atd.    
    }

    udaje = get_els(vyp, udmap, et.nsmap)
    ico = int(row['ico']) # lepsi nez - int(udaje['ico']) - da se pak dohledat

    with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute('delete from od.ares_or_udaje where ico = %s', (ico, )) # tohle kaskaduje do ostatnich tabulek
        cursor.execute('''insert into od.ares_or_udaje(ico, aktualizace_db, datum_vypisu, platnost_od, datum_zapisu, stav_subjektu)
                        values(%(ico)s, %(aktualizace_db)s, %(datum_vypisu)s, %(platnost_od)s, %(datum_zapisu)s, %(stav_subjektu)s)
                        ''', {'ico': ico, **udaje})

        # nazev subjektu (v case)
        # cursor.execute('delete from od.ares_or_nazvy where ico = %s', (ico, ))
        for el in vyp.findall('./D:ZAU/D:OF', namespaces=et.nsmap):
            of = (ico, el.attrib.get('dod'), el.attrib.get('ddo'), el.text)
            cursor.execute('''insert into od.ares_or_nazvy(ico, dod, ddo, nazev)
                            values(%s, %s, %s, %s)''', of)

        # pravni formy
        pmp = {
            'kpf': 'D:KPF',
            'npf': 'D:NPF',
            'pfo': 'D:PFO',
            'tzu': 'D:TZU',
        }
        # cursor.execute('delete from od.ares_or_pravni_formy where ico = %s', (ico, ))

        for pfobj in vyp.findall('./D:ZAU/D:PFO', namespaces=et.nsmap):
            pfo = get_els(pfobj, pmp, et.nsmap)
            pfo['od'] = pfobj.attrib.get('dod')
            pfo['do'] = pfobj.attrib.get('ddo')

            cursor.execute('''insert into od.ares_or_pravni_formy(ico, dod, ddo, kpf, npf, pfo, tzu)
                        values(%(ico)s, %(od)s, %(do)s, %(kpf)s, %(npf)s, %(pfo)s, %(tzu)s)''',
                       {'ico': ico, **pfo})
            
        # sidla
        # TODO: zbytek mappingu
        smp = {
            'stat': 'D:NS',
            'obec': 'D:N',
            'ulice': 'D:NU',
            'psc': 'D:PSC',
        }
        # cursor.execute('delete from od.ares_or_sidla where ico = %s', (ico, ))
        for siobj in vyp.findall('./D:ZAU/D:SI', namespaces=et.nsmap):
            si = get_els(siobj, smp, et.nsmap)
            si['od'] = siobj.attrib.get('dod')
            si['do'] = siobj.attrib.get('ddo')
            
            cursor.execute('''insert into od.ares_or_sidla(ico, dod, ddo, ulice, obec, stat, psc)
                            values(%(ico)s, %(od)s, %(do)s, %(ulice)s, %(obec)s, %(stat)s, %(psc)s)''',
                           {'ico': ico, **si})

        # angazovane osoby
        # http://wwwinfo.mfcr.cz/ares/xml_doc/schemas/ares/ares_datatypes/v_1.0.3/ares_datatypes_v_1.0.3.xsd
        ang = {
            'statutarni_organ': 'D:SO/D:CSO/D:C',
            'sos': 'D:SOS/D:CSS/D:C',
            'sok': 'D:SOK/D:CSK/D:C',
            'sop': 'D:SOP/D:CSP/D:C',
            'predstavenstvo': 'D:PRE/D:CPR/D:C',
            'szo': 'D:SOZ/D:CZO/D:C',
            'spravni_rada': 'D:SR/D:CSR/D:C',
            'nadace': 'D:NAD/D:OON',
            'nadacni_fond': 'D:NF/D:OOF',
            'likvidace': 'D:LI/D:LIR',
            'prokura': 'D:PRO/D:PRA',
            'reditele_ops': 'D:Reditele_ops/D:Reditel_ops',
            'dozorci_rada': 'D:DR/D:CDR/D:C',
            'kontrolni_komise': 'D:Kontrolni_komise/D:Clen_kontrolni_komise/D:C',
            'revizori': 'D:REI/D:RE',
            'spolecnici_bez_vkladu': 'D:SBV/D:SB',
            'spolecnici_s_vkladem': 'D:SSV/D:SS',
            'akcionari': 'D:AKI/D:AKR',
            'zakladatele_SP': 'D:Z_SP/D:ZSP',
            'zakladatele_OPS': 'D:Z_OPS/D:ZOPS',
            'zrizovatele_OZ': 'D:Z_OZ/D:ZOZ',
            'zrizovatele_PR': 'D:Z_PR/D:ZPR',
            'nastupci_zrizovatele': 'D:NAU/D:NAE',
            'zrizovatele_nadace': 'D:Z_N/D:ZN',
            'ved_oz': 'D:VOU/D:VOZ',
            'komanditiste': 'D:KME/D:KMA',
            'druzstevnici': 'D:DCI/D:DIK',
            'komplementari': 'D:KPI/D:CSK/D:C',
            'clenove_sdruzeni': 'D:CLS/D:CS',
        }
        # high level info
        hli = {
            'kategorie_ang': 'D:KAN', # kod angazovanosti
            'funkce': 'D:F',
            'clenstvi_zacatek': 'D:CLE/D:DZA',
            'clenstvi_konec': 'D:CLE/D:DK',
            'funkce_zacatek': 'D:VF/D:DZA',
            'funkce_konec': 'D:VF/D:DK',
        }
        # FO
        # TODO: chybi bydliste
        fomap = {
            'titul_pred': 'D:TP',
            'titul_za': 'D:TZ',
            'jmeno': 'D:J',
            'prijmeni': 'D:P',
            'datum_narozeni': 'D:DN',
        }
        # PO
        pomap = {
            'ico_ang': 'D:ICO',
            'izo_ang': 'D:IZO',
            'nazev': 'D:OF',
            'pravni_forma': 'D:NPF',
            'stat': 'D:SI/D:NS',
        }

        # cursor.execute('delete from od.ares_or_angos_fo where ico = %s', (ico, ))
        # cursor.execute('delete from od.ares_or_angos_po where ico = %s', (ico, ))
        for nm, ad in ang.items():
            for el in vyp.findall(ad, namespaces=et.nsmap):
                info = get_els(el, hli, et.nsmap)

                if ad.endswith('/D:C'):
                    # dozorci rada a stat. organy maj cleny
                    # takze platnost je o koren vyse
                    pr = el.getparent()
                    info['dod'] = pr.attrib['dod']
                    info['ddo'] = pr.attrib.get('ddo')
                else:
                    info['dod'] = el.attrib['dod']
                    info['ddo'] = el.attrib.get('ddo')
                    

                fo = el.find('D:FO', namespaces=et.nsmap)
                po = el.find('D:PO', namespaces=et.nsmap)
                if fo is not None:
                    fo_info = get_els(fo, fomap, et.nsmap)
                    cursor.execute('''insert into od.ares_or_angos_fo(ico, dod, ddo, nazev_ang, kategorie_ang, funkce,
                      clenstvi_zacatek, clenstvi_konec, funkce_zacatek, funkce_konec, titul_pred, titul_za,
                      jmeno, prijmeni, datum_narozeni) values(%(ico)s, %(dod)s, %(ddo)s, %(nazev_ang)s,
                      %(kategorie_ang)s, %(funkce)s, %(clenstvi_zacatek)s, %(clenstvi_konec)s, %(funkce_zacatek)s,
                      %(funkce_konec)s, %(titul_pred)s, %(titul_za)s, %(jmeno)s, %(prijmeni)s, %(datum_narozeni)s)''',
                      {
                          'ico': ico,
                          'nazev_ang': nm,
                          **info,
                          **fo_info
                      })

                if po is not None:
                    po_info = get_els(po, pomap, et.nsmap)
                    cursor.execute('''insert into od.ares_or_angos_po(ico, dod, ddo, nazev_ang, kategorie_ang, funkce,
                      clenstvi_zacatek, clenstvi_konec, funkce_zacatek, funkce_konec, ico_ang, izo_ang, nazev,
                      pravni_forma, stat) values(%(ico)s, %(dod)s, %(ddo)s, %(nazev_ang)s, %(kategorie_ang)s, %(funkce)s,
                      %(clenstvi_zacatek)s, %(clenstvi_konec)s, %(funkce_zacatek)s, %(funkce_konec)s, %(ico_ang)s,
                      %(izo_ang)s, %(nazev)s, %(pravni_forma)s, %(stat)s)''',
                      {
                          'ico': ico,
                          'nazev_ang': nm,
                          **info,
                          **po_info
                      })
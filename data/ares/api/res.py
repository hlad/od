# TODO: ulozit NACE bokem?
import json
import csv

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
    with conn, conn.cursor('res_read', cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute('select ico, xml from ares.raw where rejstrik = \'res\' and "xml" is not null and found is true')
        row = cursor.fetchone()
        while row:
            yield row
            row = cursor.fetchone()

hd = ['ico', 'aktualizace_db', 'datum_vypisu', 'nazev', 'pravni_forma_id', 'pravni_forma_nazev', 'datum_vzniku', 'datum_zaniku', 'sidlo_nazev_obce', 'sidlo_nazev_casti_obce', 'sidlo_ulice', 'sidlo_cislo_domovni', 'sidlo_typ_cislo_domovni', 'sidlo_cislo_orientacni', 'sidlo_psc', 'esa2010', 'esa2010t', 'kpp', 'nace']

with psycopg2.connect(database='ondrej') as conn, conn.cursor() as cursor, open('data/csv/res.csv', 'w') as fw:
    cw = csv.DictWriter(fw, fieldnames=hd)
    cw.writeheader()
    for row in tqdm(get_ico(conn)):
        et = lxml.etree.fromstring(row['xml'].tobytes())

        vyp = et.find('./are:Odpoved/D:Vypis_RES', namespaces=et.nsmap)

        udaje = {
            'aktualizace_db': './D:UVOD/D:ADB',
            'datum_vypisu': './D:UVOD/D:DVY',
            'nazev': './D:ZAU/D:OF',
            'pravni_forma_id': './D:ZAU/D:PF/D:KPF',
            'pravni_forma_nazev': './D:ZAU/D:PF/D:NPF',
            'datum_vzniku': './D:ZAU/D:DV',
            'datum_zaniku': './D:ZAU/D:DZ',
            'sidlo_nazev_obce': './D:SI/D:N', # TODO: jsou vsechny?
            'sidlo_nazev_casti_obce': './D:SI/D:NCO',
            'sidlo_ulice': './D:SI/D:NU',
            'sidlo_cislo_domovni': './D:SI/D:CD',
            'sidlo_typ_cislo_domovni': './D:SI/D:TCD',
            'sidlo_cislo_orientacni': './D:SI/D:CO',
            'sidlo_psc': './D:SI/D:PSC',
            # TODO: chceme ZUJ?
            'esa2010': './D:SU/D:Esa2010',
            'esa2010t': './D:SU/D:Esa2010t',
            'kpp': './D:SU/D:KPP',
        }

        nid = get_el_all(vyp, './D:Nace/D:NACE', et.nsmap)
        #nn = get_el_all(vyp, './D:Nace/D:Nazev_NACE', et.nsmap)

        dt = {
            'ico': row['ico'],
            **get_els(vyp, udaje, et.nsmap),
            'nace': '{%s}' % ','.join(nid),
        }
        # TODO: radsi to ulozime do CSV a pak az do DB? nebo bude tohle proste transakcni vec?
        
        # psycopg2 nepodporuje dict jako json hodnotu - musime serializovat
        for k, v in dt.items():
            if isinstance(v, dict):
                dt[k] = json.dumps(v, ensure_ascii=False)

        cw.writerow(dt)

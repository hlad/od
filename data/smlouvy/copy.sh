for fn in data/csv/*_smlouvy.csv; do
	cat $fn | psql -c 'copy smlouvy.smlouvy from stdin csv header'
done

for fn in data/csv/*_ucastnici.csv; do
	echo $fn
	cat $fn | psql -c 'copy smlouvy.smlouvy_ucastnici from stdin csv header'
done
psql < schema.sql

for fn in data/csv/*.csv; do
	cat $fn | psql -c 'copy psp.steno_psp from stdin csv header'
done

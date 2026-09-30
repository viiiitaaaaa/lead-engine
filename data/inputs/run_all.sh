cd /c/Users/User/lead-engine
export PYTHONIOENCODING=utf-8
python parsers/apify_run.py contact_info_scraper__vdrmota data/inputs/contacts.json --cap 2 --name контакты_с_сайтов > data/inputs/log_contacts.txt 2>&1 &
python parsers/apify_run.py 2gis data/inputs/2gis.json --cap 2 --name 2гис > data/inputs/log_2gis.txt 2>&1 &
python parsers/apify_run.py telegram_keyword_search_scraper__lofomachines data/inputs/telegram.json --cap 1.5 --name telegram_посёлки > data/inputs/log_tg.txt 2>&1 &
python parsers/apify_run.py cian data/inputs/cian.json --cap 1 --name циан_дома_от_100млн > data/inputs/log_cian.txt 2>&1 &
( for i in 1 2 3 4; do python parsers/apify_run.py avito data/inputs/avito$i.json --cap 0.6 --name авито_$i; done ) > data/inputs/log_avito.txt 2>&1 &
wait
echo ВСЁ

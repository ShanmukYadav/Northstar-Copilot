#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
mkdir -p data && cd data
curl -sL "https://codeload.github.com/Ganesh7699/Brazilian-E-Commerce-OList/zip/refs/heads/main" -o olist.zip
unzip -o -q olist.zip
mkdir -p olist_raw
mv Brazilian-E-Commerce-OList-main/olist_*.csv olist_raw/
mv Brazilian-E-Commerce-OList-main/product_category_name_translation.csv olist_raw/
rm -rf Brazilian-E-Commerce-OList-main olist.zip
echo "Done."
ls -la olist_raw/

@echo off 
python -m unittest discover -s tests -v > data\full.log 2>&1

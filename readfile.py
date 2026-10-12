import os  
f = open('core/config.py', encoding='utf-8').read()  
open('config_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

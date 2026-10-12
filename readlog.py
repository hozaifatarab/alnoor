import os  
f = open('core/logging_setup.py', encoding='utf-8').read()  
open('logging_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

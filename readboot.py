import os  
f = open('core/bootstrap.py', encoding='utf-8').read()  
open('bootstrap_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

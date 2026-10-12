import os  
f = open('core/auth.py', encoding='utf-8').read()  
open('auth_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

import os  
f = open('core/security.py', encoding='utf-8').read()  
open('security_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

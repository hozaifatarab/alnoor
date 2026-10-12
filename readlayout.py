import os  
f = open('ui/layout.py', encoding='utf-8').read()  
open('layout_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

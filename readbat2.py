import os  
f = open('tools/run_app.ps1', encoding='utf-8').read()  
open('run_app_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

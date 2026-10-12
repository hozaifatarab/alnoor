import os  
f = open('core/repos/settings.py', encoding='utf-8').read()  
open('settings_repo_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

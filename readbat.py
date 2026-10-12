import os  
f = open('tools/install_deps.bat', encoding='utf-8').read()  
open('install_deps_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

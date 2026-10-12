import os  
f = open('tools/backup_db.py', encoding='utf-8').read()  
open('backup_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  

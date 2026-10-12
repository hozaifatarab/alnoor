import os  
[print(open('core/migrations/'+f, encoding='utf-8').read()) for f in sorted(os.listdir('core/migrations'))]  

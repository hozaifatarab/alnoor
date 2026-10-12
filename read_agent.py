import os  
f = os.listdir('.github/agents')  
for fn in f:  
    print(fn)  
    print(open('.github/agents/'+fn, encoding='utf-8').read()[:1000])  

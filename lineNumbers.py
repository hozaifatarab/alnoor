f=open('requirements.txt',encoding='utf-8').readlines()  
out=open('lines.txt','w',encoding='utf-8')  
for i,l in enumerate(f):  
    out.write(str(i+1)+': '+repr(l)+chr(10))  
out.close()  

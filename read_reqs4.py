import io  
f = io.open('requirements.txt', encoding='utf-8').read()  
print(repr(f))  

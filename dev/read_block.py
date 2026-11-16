with open('docs/index.html', 'rb') as f:
    c = f.read()

# Read the full boardFoot JS block bytes
start = 82685
print(repr(c[start:start+600]))

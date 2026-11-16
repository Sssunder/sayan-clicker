import sys

with open(r'D:\Anti-Gravitasia\sayan-clicker\docs\index.html', encoding='utf-8') as f:
    content = f.read()

old = (
    '  $("boardFoot").textContent = on\r\n'
    '    ? (NET.user\r\n'
    '      ? "Общая доска класса: каждый заходит со своего устройства под своим логином и попадает сюда сам. Очки синхронизируются автоматически. \u270f\ufe0f \u2014 имя и аватарка, \U0001f6aa \u2014 выйти."\r\n'
    '      : "Общая доска класса: здесь все, кто зарегистрировался. Войди или зарегистрируйся \u2014 и твой прогресс тоже появится в рейтинге.")\r\n'
    '    : OFFLINE_FOOT;'
)
new = (
    '  $("boardFoot").textContent = on\r\n'
    '    ? (NET.user\r\n'
    '      ? "Общая доска класса (Supabase): каждый заходит со своего устройства под своим логином и попадает сюда сам. Очки синхронизируются автоматически. \u270f\ufe0f \u2014 имя и аватарка, \U0001f6aa \u2014 выйти."\r\n'
    '      : "Общая доска класса (Supabase): зарегистрируйся со своего устройства \u2014 и твой прогресс появится в рейтинге класса сам!")\r\n'
    '    : OFFLINE_FOOT;'
)

print('Found:', old in content)
content2 = content.replace(old, new, 1)
with open(r'D:\Anti-Gravitasia\sayan-clicker\docs\index.html', 'w', encoding='utf-8', newline='') as f:
    f.write(content2)
print('Done')

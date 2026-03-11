const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
const match = html.match(/const \{\s*([\s\S]*?)\s*\} = LucideReact;/);
if (match) {
  const icons = match[1].split(',').map(s => s.trim()).filter(Boolean);
  const https = require('https');
  https.get('https://unpkg.com/lucide-react@0.292.0/dist/umd/lucide-react.js', (res) => {
    let data = '';
    res.on('data', c => data+=c);
    res.on('end', () => {
      const window = {}; const global = window;
      eval(data.replace(/require\([^)]*\)/g, '{}'));
      const lr = global.LucideReact;
      const missing = icons.filter(i => !lr[i]);
      console.log('Missing icons:', missing);
      console.log('All icons match CheckCircle:', Object.keys(lr).filter(k => k.toLowerCase().includes('check')));
      console.log('All icons match Alert:', Object.keys(lr).filter(k => k.toLowerCase().includes('alert')));
      console.log('All icons match Arrow:', Object.keys(lr).filter(k => k.toLowerCase().includes('arrow')));
    });
  });
}

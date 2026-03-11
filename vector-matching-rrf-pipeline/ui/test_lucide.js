const https = require('https');
https.get('https://unpkg.com/lucide-react@latest/dist/umd/lucide-react.js', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const window = {};
    const global = window;
    const exports = {};
    const module = { exports };
    const require = () => ({createElement: () => {}, forwardRef: () => {}});
    try {
      eval(data);
      const icons = global.LucideReact || window.LucideReact;
      const needed = ['LayoutTemplate', 'Search', 'Filter', 'CheckCircle2', 'AlertCircle', 'HelpCircle', 'FileQuestion', 'Check', 'X', 'AlertTriangle', 'ArrowRightLeft', 'Factory', 'Tag', 'DollarSign', 'Bot'];
      const missing = needed.filter(i => !icons[i]);
      console.log('Missing:', missing);
    } catch(e) { console.error(e.message); }
  });
});

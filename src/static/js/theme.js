(function () {
    var STORAGE_KEY = 'digiana-theme';
    var html = document.documentElement;

    function getTheme() {
        return localStorage.getItem(STORAGE_KEY) || 'dark';
    }

    function applyTheme(theme) {
        if (theme === 'light') {
            html.classList.add('light-mode');
        } else {
            html.classList.remove('light-mode');
        }

        var btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.checked = (theme === 'light');
        }

        var logo = document.getElementById('digiana-logo');
        if (logo) {
            logo.src = theme === 'light' ? logo.dataset.light : logo.dataset.dark;
        }
    }

    function toggle() {
        var current = getTheme();
        var next = current === 'dark' ? 'light' : 'dark';
        localStorage.setItem(STORAGE_KEY, next);
        applyTheme(next);
    }

    /* Aplica o tema imediatamente (evita flash de tema errado) */
    applyTheme(getTheme());

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('change', toggle);
        }
        /* Re-aplica após o DOM estar pronto para atualizar ícone e logo */
        applyTheme(getTheme());
    });
})();

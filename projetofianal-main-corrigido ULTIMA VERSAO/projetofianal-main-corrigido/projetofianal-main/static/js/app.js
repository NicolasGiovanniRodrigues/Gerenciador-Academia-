// Mostra ou esconde a senha, sem bibliotecas extras.
var botoesSenha = document.querySelectorAll('.show-password');
for (var i = 0; i < botoesSenha.length; i++) {
    botoesSenha[i].addEventListener('click', function () {
        var campo = this.closest('.password-field').querySelector('input');
        if (campo.type === 'password') {
            campo.type = 'text';
            this.setAttribute('aria-label', 'Ocultar senha');
        } else {
            campo.type = 'password';
            this.setAttribute('aria-label', 'Mostrar senha');
        }
    });
}

// Retira letras e pontuação e mantém o limite de números do campo.
function somenteNumeros(valor, limite) {
    var numeros = '';
    for (var posicao = 0; posicao < valor.length; posicao++) {
        var caractere = valor[posicao];
        if (caractere >= '0' && caractere <= '9') {
            numeros += caractere;
        }
    }
    return numeros.slice(0, limite);
}

// CPF e telefone aceitam somente números, inclusive ao colar um texto.
var camposNumericos = document.querySelectorAll('[data-numeros]');
for (var i = 0; i < camposNumericos.length; i++) {
    camposNumericos[i].addEventListener('input', function () {
        var limite = Number(this.getAttribute('data-numeros'));
        this.value = somenteNumeros(this.value, limite);
    });
    camposNumericos[i].addEventListener('paste', function (evento) {
        evento.preventDefault();
        var texto = evento.clipboardData.getData('text');
        var antes = this.value.slice(0, this.selectionStart);
        var depois = this.value.slice(this.selectionEnd);
        var limite = Number(this.getAttribute('data-numeros'));
        this.value = somenteNumeros(antes + texto + depois, limite);
    });
}

// Quantidades são inteiras: não permitem sinal, vírgula, ponto ou notação com e.
var quantidades = document.querySelectorAll('[data-inteiro]');
for (var i = 0; i < quantidades.length; i++) {
    quantidades[i].addEventListener('keydown', function (evento) {
        if (evento.key === 'e' || evento.key === 'E' || evento.key === '+' ||
                evento.key === '-' || evento.key === '.' || evento.key === ',') {
            evento.preventDefault();
        }
    });
    quantidades[i].addEventListener('input', function () {
        for (var posicao = 0; posicao < this.value.length; posicao++) {
            if (this.value[posicao] < '0' || this.value[posicao] > '9') {
                this.value = '';
                break;
            }
        }
    });
}

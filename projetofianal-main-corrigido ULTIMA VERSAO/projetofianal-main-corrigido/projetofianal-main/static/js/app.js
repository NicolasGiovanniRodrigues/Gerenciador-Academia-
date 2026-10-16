// Apenas alterna a visibilidade da senha. A validação real fica no servidor.
document.querySelectorAll('.show-password').forEach(button=>button.addEventListener('click',()=>{
  const input=button.closest('.password-field').querySelector('input');
  input.type=input.type==='password'?'text':'password';
  button.setAttribute('aria-label',input.type==='password'?'Mostrar senha':'Ocultar senha');
}));

import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

const EMAIL_COM_DOMINIO_PATTERN = /^[^\s@]+@[^\s@.]+\.[^\s@]+$/;

// O Pydantic EmailStr exige um domínio com ponto, regra que Validators.email não cobre em todos os casos.
export const emailComDominioValido: ValidatorFn = (
  control: AbstractControl,
): ValidationErrors | null => {
  const valor = String(control.value ?? '').trim();
  if (!valor) return null;
  return EMAIL_COM_DOMINIO_PATTERN.test(valor) ? null : { emailDominioInvalido: true };
};

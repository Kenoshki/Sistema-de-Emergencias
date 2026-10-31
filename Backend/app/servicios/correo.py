"""
Envío de correo para la recuperación de contraseña.

Proveedores, en este orden:
1. Resend (API HTTPS, RESEND_API_KEY): recomendado en Railway, que bloquea SMTP
   en los planes Free/Hobby.
2. SMTP (SMTP_HOST...).
3. Sin proveedor: se avisa en el log (y, solo con DEBUG_MODE, se imprime el enlace).
"""
import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape

from app.config import settings

log = logging.getLogger("uvicorn.error")


def correo_configurado() -> bool:
    return bool(settings.RESEND_API_KEY or settings.SMTP_HOST)


def _enviar_resend(destino: str, asunto: str, texto: str, html: str) -> None:
    cuerpo = json.dumps({"from": settings.MAIL_FROM, "to": [destino], "subject": asunto,
                         "text": texto, "html": html}).encode("utf-8")
    peticion = urllib.request.Request(
        "https://api.resend.com/emails", data=cuerpo, method="POST",
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(peticion, timeout=15) as r:  # noqa: S310 (URL fija https)
        r.read()


def _enviar_smtp(destino: str, asunto: str, texto: str, html: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.MAIL_FROM
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_TLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg, to_addrs=[parseaddr(destino)[1]])


def enviar_correo(destino: str, asunto: str, texto: str, html: str) -> bool:
    """Devuelve True si se entregó al proveedor. Nunca lanza: se ejecuta en segundo plano."""
    try:
        if settings.RESEND_API_KEY:
            _enviar_resend(destino, asunto, texto, html)
        elif settings.SMTP_HOST:
            _enviar_smtp(destino, asunto, texto, html)
        else:
            log.warning("Correo no configurado (RESEND_API_KEY o SMTP_HOST): no se envió '%s'.", asunto)
            if settings.DEBUG_MODE:
                log.warning("[DEBUG] Mensaje para %s:\n%s", destino, texto)
            return False
        return True
    except (urllib.error.URLError, smtplib.SMTPException, OSError) as exc:
        log.error("Falló el envío de correo a un usuario: %s", exc)
        return False


def enviar_recuperacion(destino: str, nombre: str, enlace: str, minutos: int) -> bool:
    saludo = f"Hola {nombre}," if nombre else "Hola,"
    texto = (
        f"{saludo}\n\nRecibimos una solicitud para restablecer la contraseña de su cuenta del "
        f"Sistema de Gestión de Emergencias.\n\nAbra este enlace (vence en {minutos} minutos y solo sirve una vez):\n"
        f"{enlace}\n\nSi usted no lo solicitó, ignore este mensaje: su contraseña no cambiará."
    )
    html = (
        f"<p>{escape(saludo)}</p><p>Recibimos una solicitud para restablecer la contraseña de su cuenta del "
        f"Sistema de Gestión de Emergencias.</p>"
        f'<p><a href="{escape(enlace)}">Restablecer mi contraseña</a></p>'
        f"<p>El enlace vence en {minutos} minutos y solo sirve una vez.</p>"
        f"<p>Si usted no lo solicitó, ignore este mensaje: su contraseña no cambiará.</p>"
    )
    return enviar_correo(destino, "Restablecer su contraseña – Emergencias", texto, html)

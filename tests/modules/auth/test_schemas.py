from app.modules.auth.schemas import EmailPasswordForm


def test_email_password_form_assigns_fields():
    form = EmailPasswordForm(email="user@example.com", password="secret")
    assert form.email == "user@example.com"
    assert form.password == "secret"

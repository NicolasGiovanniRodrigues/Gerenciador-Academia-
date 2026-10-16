# Importações
import os
import re
import secrets
from datetime import date, time
import fdb
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_bcrypt import Bcrypt

# Inicia a aplicação
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["CSRF_ENABLED"] = True
bcrypt = Bcrypt(app)
PERFIS = {"ALUNO": "Aluno", "PERSONAL": "Professor", "ADMINISTRADOR": "Administrador"}


# Conecta ao banco Firebird que está na pasta do projeto
def conectar():
    if os.getenv("FIREBIRD_CLIENT"):
        fdb.load_api(os.environ["FIREBIRD_CLIENT"])
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BANCO.FDB")
    con = fdb.connect(
        host=os.getenv("DB_HOST", "localhost") or None,
        database=caminho,
        user=os.getenv("DB_USER", "SYSDBA"),
        password=os.getenv("DB_PASSWORD", "sysdba"),
        charset="UTF8",
    )
    con.default_tpb = fdb.ISOLATION_LEVEL_READ_COMMITED
    return con


# Organiza o resultado da consulta para usar os nomes dos campos no HTML
def consultar(con, sql, parametros=(), unico=False):
    cursor = con.cursor()
    cursor.execute(sql, parametros)
    campos = []
    for coluna in cursor.description:
        campos.append(coluna[0].lower())
    dados = []
    for registro in cursor.fetchall():
        dados.append(dict(zip(campos, registro)))
    if unico:
        if dados:
            return dados[0]
        return None
    return dados


# Confere se a senha é forte, sem biblioteca de validação
def senha_forte(senha):
    if len(senha) < 8 or len(senha.encode("utf-8")) > 72:
        return False
    maiuscula = False
    minuscula = False
    numero = False
    especial = False
    for letra in senha:
        if letra.isupper():
            maiuscula = True
        if letra.islower():
            minuscula = True
        if letra.isdigit():
            numero = True
        if not letra.isalnum() and (not letra.isspace()):
            especial = True
    return maiuscula and minuscula and numero and especial


# Compara a senha digitada com o hash salvo no banco
def conferir_senha(hash_salvo, senha):
    if not hash_salvo or len(senha.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.check_password_hash(hash_salvo, senha)
    except (ValueError, TypeError):
        return False


# Protege a senha antes de gravar no banco
def gerar_hash(senha):
    return bcrypt.generate_password_hash(senha).decode("utf-8")


# Confere o formulário, a sessão e o perfil antes de abrir uma página
@app.before_request
def verificar_requisicao():
    g.usuario = None
    if request.method == "POST" and app.config["CSRF_ENABLED"]:
        token = request.form.get("csrf_token", "")
        if not token or not secrets.compare_digest(
            token, session.get("csrf_token", "")
        ):
            abort(
                400,
                description="Formulário expirado. Recarregue a página e tente novamente.",
            )
    if request.endpoint in ("index", "login", "cadastro", "static", None):
        return None
    if not session.get("id_usuario"):
        return redirect(url_for("login"))
    con = conectar()
    try:
        g.usuario = consultar(
            con,
            "SELECT * FROM USUARIOS WHERE ID_USUARIO=?",
            (session["id_usuario"],),
            True,
        )
    finally:
        con.close()
    if not g.usuario or not g.usuario["ativo"] or g.usuario["bloqueado"]:
        session.clear()
        g.usuario = None
        flash("Faça login com uma conta ativa e liberada.", "erro")
        return redirect(url_for("login"))
    permissoes = {
        "logout": (),
        "voltar_home": (),
        "administrador": ("ADMINISTRADOR",),
        "aluno": ("ALUNO",),
        "personal": ("PERSONAL",),
        "agenda": ("PERSONAL",),
        "presencas": ("PERSONAL",),
        "perfil": (),
        "editar_dados": (),
        "alterar_senha": (),
        "usuarios": ("ADMINISTRADOR",),
        "usuario_form": ("ADMINISTRADOR",),
        "modalidades": ("ADMINISTRADOR",),
        "modalidade_form": ("ADMINISTRADOR",),
        "modalidade_excluir": ("ADMINISTRADOR",),
        "aulas": ("ADMINISTRADOR",),
        "aula_form": ("ADMINISTRADOR",),
        "aula_detalhes": (),
        "aula_cancelar": ("ADMINISTRADOR",),
        "inscrever": ("ALUNO",),
        "minhas_aulas": ("ALUNO",),
        "cancelar_inscricao": ("ALUNO",),
        "chamada": ("ADMINISTRADOR", "PERSONAL"),
    }
    permitidos = permissoes.get(request.endpoint, ())
    if permitidos and g.usuario["tipo_usuario"] not in permitidos:
        abort(403)


# Envia os dados da conta e o token do formulário para as telas
@app.context_processor
def contexto():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    return dict(
        usuario=g.get("usuario"), perfis=PERFIS, csrf_token=session["csrf_token"]
    )


# Evita manter páginas da conta no cache após sair
@app.after_request
def cabecalhos(response):
    if g.get("usuario") or request.endpoint in ("login", "logout"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# Mostra uma mensagem e retorna para a página indicada
def falha(mensagem, destino, **valores):
    flash(mensagem, "erro")
    return redirect(url_for(destino, **valores))


# Confere os dados recebidos do formulário de usuário
def ler_pessoa(form):
    nome = form.get("nome", "").strip()
    email = form.get("email", "").strip().lower()
    telefone = form.get("telefone", "").strip()
    cpf = re.sub("\\D", "", form.get("cpf", ""))
    nascimento = form.get("data_nascimento", "")
    if (
        not nome
        or len(nome) > 254
        or (not re.fullmatch("[^\\s@]+@[^\\s@]+\\.[^\\s@]+", email))
        or (len(email) > 100)
    ):
        raise ValueError("Informe nome e e-mail válidos.")
    if len(telefone) > 20 or (cpf and len(cpf) != 11):
        raise ValueError("Confira o telefone e o CPF (11 números).")
    try:
        nascimento = date.fromisoformat(nascimento) if nascimento else None
    except ValueError:
        raise ValueError("Data de nascimento inválida.")
    if nascimento and nascimento > date.today():
        raise ValueError("A data de nascimento não pode ser futura.")
    return (nome, email, telefone, cpf, nascimento)


# Confere a força da nova senha e as três senhas anteriores
def validar_nova_senha(con, id_usuario, senha):
    if not senha_forte(senha):
        raise ValueError(
            "Use pelo menos 8 caracteres, maiúscula, minúscula, número e símbolo (até 72 bytes)."
        )
    if id_usuario:
        atual = consultar(
            con, "SELECT SENHA FROM USUARIOS WHERE ID_USUARIO=?", (id_usuario,), True
        )
        if atual and conferir_senha(atual["senha"], senha):
            raise ValueError(
                "Você não pode repetir a senha atual ou as três últimas senhas."
            )
        ultimas = consultar(
            con,
            """
                SELECT FIRST 3 SENHA
                FROM HISTORICO_SENHAS
                WHERE ID_USUARIO=?
                ORDER BY ID_HISTORICO DESC
            """,
            (id_usuario,),
        )
        for registro in ultimas:
            if conferir_senha(registro["senha"], senha):
                raise ValueError("Você não pode repetir as três últimas senhas.")
    return gerar_hash(senha)


# Guarda a senha antiga no histórico, sempre protegida
def guardar_senha(con, id_usuario, hash_senha):
    cursor = con.cursor()
    cursor.execute(
        "INSERT INTO HISTORICO_SENHAS (ID_USUARIO, SENHA) VALUES (?, ?)",
        (id_usuario, hash_senha),
    )


# Abre a página inicial do site
@app.route("/")
def index():
    return render_template("landing.html")


# Cadastra uma nova conta de aluno
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        try:
            nome, email, telefone, cpf, nascimento = ler_pessoa(request.form)
            senha = request.form.get("senha", "")
            if not cpf or not nascimento:
                raise ValueError("Preencha CPF e data de nascimento.")
            if senha != request.form.get("confirmar_senha"):
                raise ValueError("As senhas não coincidem.")
            con = conectar()
            try:
                if consultar(
                    con,
                    "SELECT ID_USUARIO FROM USUARIOS WHERE LOWER(TRIM(EMAIL))=?",
                    (email,),
                    True,
                ):
                    raise ValueError("Este e-mail já está cadastrado.")
                hash_senha = validar_nova_senha(con, None, senha)
                cursor = con.cursor()

                # Cadastra o usuário
                cursor.execute(
                    """
                    INSERT INTO USUARIOS (
                        NOME, EMAIL, TELEFONE, CPF, DATA_NASCIMENTO,
                        SENHA, TIPO_USUARIO, ATIVO, BLOQUEADO, TENTATIVAS_LOGIN
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'ALUNO', 1, 0, 0)
                    """,
                    (nome, email, telefone, cpf, nascimento, hash_senha),
                )

                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash("Cadastro realizado com sucesso! Faça seu login.", "sucesso")
            return redirect(url_for("login"))
        except ValueError as e:
            flash(str(e), "erro")
        except fdb.IntegrityError:
            flash("Este e-mail ou CPF já está cadastrado.", "erro")
    return render_template("cadastro.html")


# Faz o login e bloqueia a conta após três erros
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        con = conectar()
        try:
            u = consultar(
                con,
                "SELECT * FROM USUARIOS WHERE LOWER(TRIM(EMAIL))=? WITH LOCK",
                (email,),
                True,
            )
            if not u:
                flash("E-mail ou senha incorretos.", "erro")
            elif not u["ativo"]:
                flash("Usuário inativo.", "erro")
            elif u["bloqueado"]:
                flash("Usuário bloqueado. Procure o administrador.", "erro")
            elif conferir_senha(u["senha"], senha):
                cursor = con.cursor()
                cursor.execute(
                    "UPDATE USUARIOS SET TENTATIVAS_LOGIN=0 WHERE ID_USUARIO=?",
                    (u["id_usuario"],),
                )
                session.clear()
                session["id_usuario"] = u["id_usuario"]
                con.commit()
                return redirect(url_for("voltar_home"))
            else:
                tentativas = (u["tentativas_login"] or 0) + 1
                cursor = con.cursor()
                cursor.execute(
                    """
                        UPDATE USUARIOS
                        SET TENTATIVAS_LOGIN=?,
                            BLOQUEADO=?
                        WHERE ID_USUARIO=?
                    """,
                    (tentativas, int(tentativas >= 3), u["id_usuario"]),
                )
                flash(
                    (
                        "Usuário bloqueado após 3 tentativas erradas."
                        if tentativas >= 3
                        else f"E-mail ou senha incorretos. Restam {3 - tentativas} tentativas."
                    ),
                    "erro",
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    return render_template("login.html")


# Encerra a sessão da conta
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("login"))


# Abre a página inicial do perfil conectado
@app.route("/minha-home")
def voltar_home():
    return redirect(
        url_for(
            {
                "ALUNO": "aluno",
                "PERSONAL": "personal",
                "ADMINISTRADOR": "administrador",
            }[g.usuario["tipo_usuario"]]
        )
    )


AULAS_SQL = """
    SELECT A.*,
           M.NOME AS MODALIDADE,
           U.NOME AS PROFESSOR,
        (SELECT COUNT(*)
         FROM INSCRICOES I
         WHERE I.ID_AULA=A.ID_AULA
             AND I.ATIVA=1) AS INSCRITOS
    FROM AULAS A
    JOIN MODALIDADES M ON M.ID_MODALIDADE=A.ID_MODALIDADE
    JOIN USUARIOS U ON U.ID_USUARIO=A.ID_PROFESSOR
"""


# Mostra o início do administrador
@app.route("/administrador")
def administrador():
    con = conectar()
    try:
        contagens = {
            p: consultar(
                con,
                "SELECT COUNT(*) AS TOTAL FROM USUARIOS WHERE TIPO_USUARIO=?",
                (p,),
                True,
            )["total"]
            for p in ("ALUNO", "PERSONAL")
        }
        modalidades = consultar(
            con, "SELECT COUNT(*) AS TOTAL FROM MODALIDADES", unico=True
        )["total"]
        aulas = consultar(
            con,
            AULAS_SQL
            + " WHERE A.DATA_AULA>=CURRENT_DATE AND A.SITUACAO='AGENDADA' ORDER BY A.DATA_AULA, A.HORA_INICIO",
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "dashboard.html",
        contagens=contagens,
        modalidades=modalidades,
        aulas=aulas,
        hoje=date.today(),
    )


# Mostra a grade de aulas disponíveis para o aluno
@app.route("/aluno")
def aluno():
    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + " WHERE A.DATA_AULA>=CURRENT_DATE AND A.SITUACAO='AGENDADA' AND M.ATIVA=1 ORDER BY A.DATA_AULA, A.HORA_INICIO",
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("grade.html", aulas=aulas)


# Mostra o início do professor
@app.route("/personal")
def personal():
    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + " WHERE A.ID_PROFESSOR=? ORDER BY A.DATA_AULA DESC, A.HORA_INICIO",
            (g.usuario["id_usuario"],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("personal.html", aulas=aulas, hoje=date.today())


# Lista as aulas do professor conectado
@app.route("/agenda")
def agenda():
    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL + " WHERE A.ID_PROFESSOR=? ORDER BY A.DATA_AULA,A.HORA_INICIO",
            (g.usuario["id_usuario"],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("aulas.html", aulas=aulas, titulo="Minha Agenda e Aulas")


# Seleciona uma aula do professor para registrar a chamada
@app.route("/presencas")
def presencas():
    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + " WHERE A.ID_PROFESSOR=? ORDER BY A.DATA_AULA DESC,A.HORA_INICIO",
            (g.usuario["id_usuario"],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "aulas.html", aulas=aulas, titulo="Selecionar aula para chamada"
    )


# Mostra os dados da própria conta
@app.route("/perfil")
def perfil():
    return render_template(
        "perfil.html",
        titulo=(
            "Minha conta"
            if g.usuario["tipo_usuario"] == "ADMINISTRADOR"
            else "Meu Perfil"
        ),
    )


# Edita os dados pessoais sem alterar o código do usuário
@app.route("/editar-dados", methods=["GET", "POST"])
def editar_dados():
    if request.method == "POST":
        try:
            valores = ler_pessoa(request.form)
            con = conectar()
            try:
                if consultar(
                    con,
                    """
                        SELECT ID_USUARIO
                        FROM USUARIOS
                        WHERE LOWER(TRIM(EMAIL))=?
                            AND ID_USUARIO<>?
                    """,
                    (valores[1], g.usuario["id_usuario"]),
                    True,
                ):
                    raise ValueError("Este e-mail já está cadastrado.")
                cursor = con.cursor()
                cursor.execute(
                    """
                        UPDATE USUARIOS
                        SET NOME=?,
                            EMAIL=?,
                            TELEFONE=?,
                            CPF=?,
                            DATA_NASCIMENTO=?
                        WHERE ID_USUARIO=?
                    """,
                    (*valores, g.usuario["id_usuario"]),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash("Dados atualizados com sucesso!", "sucesso")
            return redirect(url_for("perfil"))
        except ValueError as e:
            flash(str(e), "erro")
        except fdb.IntegrityError:
            flash("E-mail ou CPF já cadastrado.", "erro")
    return render_template(
        "usuario_form.html", pessoa=g.usuario, proprio=True, titulo="Editar meus dados"
    )


# Confere a senha atual e grava a nova senha protegida
@app.route("/alterar-senha", methods=["GET", "POST"])
def alterar_senha():
    if request.method == "POST":
        try:
            if not conferir_senha(
                g.usuario["senha"], request.form.get("senha_atual", "")
            ):
                raise ValueError("A senha atual está incorreta.")
            nova = request.form.get("nova_senha", "")
            if nova != request.form.get("confirmar", ""):
                raise ValueError("As novas senhas não coincidem.")
            con = conectar()
            try:
                hash_senha = validar_nova_senha(con, g.usuario["id_usuario"], nova)
                guardar_senha(con, g.usuario["id_usuario"], g.usuario["senha"])
                cursor = con.cursor()
                cursor.execute(
                    "UPDATE USUARIOS SET SENHA=? WHERE ID_USUARIO=?",
                    (hash_senha, g.usuario["id_usuario"]),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash("Senha alterada com sucesso!", "sucesso")
            return redirect(url_for("perfil"))
        except ValueError as e:
            flash(str(e), "erro")
    return render_template("alterar_senha.html")


# Lista os usuários do perfil selecionado
@app.route("/usuarios")
def usuarios():
    filtro = request.args.get("perfil", "ALUNO")
    if filtro not in PERFIS:
        abort(400)
    con = conectar()
    try:
        pessoas = consultar(
            con, "SELECT * FROM USUARIOS WHERE TIPO_USUARIO=? ORDER BY NOME", (filtro,)
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "usuarios.html",
        pessoas=pessoas,
        filtro=filtro,
        titulo={
            "ALUNO": "Alunos",
            "PERSONAL": "Professores",
            "ADMINISTRADOR": "Administradores",
        }[filtro],
    )


# Cadastra ou edita usuários na área do administrador
@app.route("/usuarios/novo", methods=["GET", "POST"])
@app.route("/usuarios/<int:id_usuario>/editar", methods=["GET", "POST"])
def usuario_form(id_usuario=None):
    con = conectar()
    try:
        pessoa = (
            consultar(
                con, "SELECT * FROM USUARIOS WHERE ID_USUARIO=?", (id_usuario,), True
            )
            if id_usuario
            else {}
        )
        if id_usuario and (not pessoa):
            abort(404)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if request.method == "POST":
        try:
            valores = ler_pessoa(request.form)
            tipo = request.form.get("tipo_usuario", "ALUNO")
            if tipo not in PERFIS:
                raise ValueError("Perfil de usuário inválido.")
            ativo = int(request.form.get("ativo", "0") == "1")
            bloqueado = int(request.form.get("bloqueado", "0") == "1")
            try:
                tentativas = int(request.form.get("tentativas_login", "0"))
            except ValueError:
                raise ValueError("Tentativas de login inválidas.")
            if not 0 <= tentativas <= 2147483647:
                raise ValueError("Tentativas de login inválidas.")
            senha = request.form.get("senha", "")
            con = conectar()
            try:
                if consultar(
                    con,
                    """
                        SELECT ID_USUARIO
                        FROM USUARIOS
                        WHERE LOWER(TRIM(EMAIL))=?
                            AND ID_USUARIO<>?
                    """,
                    (valores[1], id_usuario or 0),
                    True,
                ):
                    raise ValueError("Este e-mail já está cadastrado.")
                hash_senha = (
                    validar_nova_senha(con, id_usuario, senha)
                    if senha or not id_usuario
                    else pessoa["senha"]
                )
                if id_usuario:
                    cursor = con.cursor()
                    cursor.execute(
                        """
                            UPDATE USUARIOS
                            SET NOME=?,
                                EMAIL=?,
                                TELEFONE=?,
                                CPF=?,
                                DATA_NASCIMENTO=?,
                                TIPO_USUARIO=?,
                                ATIVO=?,
                                BLOQUEADO=?,
                                TENTATIVAS_LOGIN=?,
                                SENHA=?
                            WHERE ID_USUARIO=?
                        """,
                        (
                            *valores,
                            tipo,
                            ativo,
                            bloqueado,
                            tentativas,
                            hash_senha,
                            id_usuario,
                        ),
                    )
                    if senha:
                        guardar_senha(con, id_usuario, pessoa["senha"])
                else:
                    cursor = con.cursor()
                    cursor.execute(
                        """
                            INSERT INTO USUARIOS (NOME, EMAIL, TELEFONE, CPF, DATA_NASCIMENTO, TIPO_USUARIO, ATIVO, BLOQUEADO, TENTATIVAS_LOGIN, SENHA)
                            VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING ID_USUARIO
                        """,
                        (*valores, tipo, ativo, bloqueado, tentativas, hash_senha),
                    )
                    id_usuario = cursor.fetchone()[0]
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash("Usuário salvo com sucesso!", "sucesso")
            return redirect(url_for("usuarios", perfil=tipo))
        except ValueError as e:
            flash(str(e), "erro")
        except fdb.IntegrityError:
            flash("Este e-mail ou CPF já está cadastrado.", "erro")
    return render_template(
        "usuario_form.html",
        pessoa=pessoa,
        proprio=False,
        titulo="Editar usuário" if id_usuario else "Cadastrar usuário",
    )


# Lista as modalidades ativas e inativas
@app.route("/modalidades")
def modalidades():
    con = conectar()
    try:
        lista = consultar(
            con,
            """
                SELECT M.*,
                    (SELECT COUNT(*)
                     FROM AULAS A
                     WHERE A.ID_MODALIDADE=M.ID_MODALIDADE) AS TOTAL_AULAS
                FROM MODALIDADES M
                ORDER BY M.NOME
            """,
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("modalidades.html", modalidades=lista)


# Cadastra ou edita uma modalidade sem repetir o nome
@app.route("/modalidades/nova", methods=["GET", "POST"])
@app.route("/modalidades/<int:id_modalidade>/editar", methods=["GET", "POST"])
def modalidade_form(id_modalidade=None):
    con = conectar()
    try:
        item = (
            consultar(
                con,
                "SELECT * FROM MODALIDADES WHERE ID_MODALIDADE=?",
                (id_modalidade,),
                True,
            )
            if id_modalidade
            else {}
        )
        if id_modalidade and (not item):
            abort(404)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        try:
            try:
                duracao = int(request.form.get("duracao", "0"))
            except ValueError:
                raise ValueError(
                    "Duração inválida. Informe um número inteiro de minutos."
                )
            if (
                not nome
                or len(nome) > 100
                or (not descricao)
                or (len(descricao) > 500)
                or (not 0 < duracao <= 2147483647)
            ):
                raise ValueError("Preencha nome, descrição e duração maior que zero.")
            con = conectar()
            try:
                if consultar(
                    con,
                    """
                        SELECT ID_MODALIDADE
                        FROM MODALIDADES
                        WHERE LOWER(TRIM(NOME))=?
                            AND ID_MODALIDADE<>?
                    """,
                    (nome.lower(), id_modalidade or 0),
                    True,
                ):
                    raise ValueError("Modalidade já existe.")
                valores = (
                    nome,
                    descricao,
                    duracao,
                    int(request.form.get("ativa", "1") == "1"),
                )
                if id_modalidade:
                    cursor = con.cursor()
                    cursor.execute(
                        """
                            UPDATE MODALIDADES
                            SET NOME=?,
                                DESCRICAO=?,
                                DURACAO=?,
                                ATIVA=?
                            WHERE ID_MODALIDADE=?
                        """,
                        (*valores, id_modalidade),
                    )
                else:
                    cursor = con.cursor()
                    cursor.execute(
                        """
                            INSERT INTO MODALIDADES (NOME, DESCRICAO, DURACAO, ATIVA)
                            VALUES (?,?,?,?)
                        """,
                        valores,
                    )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash("Modalidade salva com sucesso!", "sucesso")
            return redirect(url_for("modalidades"))
        except ValueError as e:
            flash(str(e) if str(e) else "Duração inválida.", "erro")
        except fdb.IntegrityError:
            flash("Modalidade já existe.", "erro")
    return render_template(
        "modalidade_form.html",
        item=item,
        titulo="Editar Modalidade" if id_modalidade else "Nova modalidade",
    )


# Exclui a modalidade somente se ela não tiver aulas vinculadas
@app.route("/modalidades/<int:id_modalidade>/excluir", methods=["GET", "POST"])
def modalidade_excluir(id_modalidade):
    con = conectar()
    try:
        item = consultar(
            con,
            "SELECT * FROM MODALIDADES WHERE ID_MODALIDADE=?",
            (id_modalidade,),
            True,
        )
        if not item:
            abort(404)
        if request.method == "POST":
            if consultar(
                con,
                "SELECT FIRST 1 ID_AULA FROM AULAS WHERE ID_MODALIDADE=?",
                (id_modalidade,),
                True,
            ):
                con.commit()
                return falha(
                    "Não é possível excluir: a modalidade possui aulas vinculadas.",
                    "modalidades",
                )
            cursor = con.cursor()
            cursor.execute(
                "DELETE FROM MODALIDADES WHERE ID_MODALIDADE=?", (id_modalidade,)
            )
            flash("Modalidade excluída com sucesso!", "sucesso")
            con.commit()
            return redirect(url_for("modalidades"))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "confirmar.html",
        titulo="Excluir modalidade",
        mensagem=f"Excluir a modalidade {item['nome']}? Esta ação não pode ser desfeita.",
        voltar=url_for("modalidades"),
        botao="Excluir modalidade",
    )


# Lista as aulas cadastradas
@app.route("/aulas")
def aulas():
    con = conectar()
    try:
        lista = consultar(con, AULAS_SQL + " ORDER BY A.DATA_AULA DESC,A.HORA_INICIO")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("aulas.html", aulas=lista, titulo="Aulas")


# Confere modalidade, professor, horário e capacidade da aula
def validar_aula(con, id_aula=None):
    try:
        nome = request.form.get("nome", "").strip()
        modalidade = int(request.form.get("id_modalidade", "0"))
        professor = int(request.form.get("id_professor", "0"))
        dia = date.fromisoformat(request.form.get("data_aula", ""))
        inicio = time.fromisoformat(request.form.get("hora_inicio", ""))
        fim = time.fromisoformat(request.form.get("hora_fim", ""))
        capacidade = int(request.form.get("capacidade", "0"))
        local = request.form.get("local", "").strip()
    except ValueError:
        raise ValueError("Preencha data, horários e números válidos.")
    if not 0 < modalidade <= 2147483647 or not 0 < professor <= 2147483647:
        raise ValueError("Selecione uma modalidade e um professor válidos.")
    if not nome or len(nome) > 100 or (not local) or (len(local) > 100):
        raise ValueError("Preencha nome da aula e local.")
    if not 0 < capacidade <= 2147483647:
        raise ValueError(
            "Capacidade inválida. Informe um número inteiro maior que zero."
        )
    if fim <= inicio:
        raise ValueError("O horário de término deve ser maior que o horário de início.")
    if not consultar(
        con,
        """
            SELECT ID_MODALIDADE
            FROM MODALIDADES
            WHERE ID_MODALIDADE=?
                AND ATIVA=1
        """,
        (modalidade,),
        True,
    ):
        raise ValueError("Selecione uma modalidade cadastrada e ativa.")
    if not consultar(
        con,
        """
            SELECT ID_USUARIO
            FROM USUARIOS
            WHERE ID_USUARIO=?
                AND TIPO_USUARIO='PERSONAL'
                AND ATIVO=1
        """,
        (professor,),
        True,
    ):
        raise ValueError("Instrutor não permitido. Selecione um Professor ativo.")
    consultar(
        con,
        "SELECT ID_USUARIO FROM USUARIOS WHERE ID_USUARIO=? WITH LOCK",
        (professor,),
        True,
    )
    if consultar(
        con,
        """
            SELECT ID_AULA
            FROM AULAS
            WHERE ID_PROFESSOR=?
                AND DATA_AULA=?
                AND HORA_INICIO<?
                AND HORA_FIM>?
                AND SITUACAO='AGENDADA'
                AND ID_AULA<>?
        """,
        (professor, dia, fim, inicio, id_aula or 0),
        True,
    ):
        raise ValueError("O professor já possui aula nesse dia e horário.")
    if id_aula:
        total = consultar(
            con,
            """
                SELECT COUNT(*) AS TOTAL
                FROM INSCRICOES
                WHERE ID_AULA=?
                    AND ATIVA=1
            """,
            (id_aula,),
            True,
        )["total"]
        if capacidade < total:
            raise ValueError("Capacidade inválida: inferior ao número de inscritos.")
    return (nome, modalidade, professor, dia, inicio, fim, capacidade, local)


# Cadastra ou edita os dados da aula
@app.route("/aulas/nova", methods=["GET", "POST"])
@app.route("/aulas/<int:id_aula>/editar", methods=["GET", "POST"])
def aula_form(id_aula=None):
    con = conectar()
    try:
        item = (
            consultar(con, "SELECT * FROM AULAS WHERE ID_AULA=?", (id_aula,), True)
            if id_aula
            else {}
        )
        if id_aula and (not item):
            abort(404)
        modos = consultar(con, "SELECT * FROM MODALIDADES WHERE ATIVA=1 ORDER BY NOME")
        professores = consultar(
            con,
            """
                SELECT ID_USUARIO,
                       NOME
                FROM USUARIOS
                WHERE TIPO_USUARIO='PERSONAL'
                    AND ATIVO=1
                ORDER BY NOME
            """,
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if request.method == "POST":
        try:
            con = conectar()
            try:
                valores = validar_aula(con, id_aula)
                if id_aula:
                    cursor = con.cursor()
                    cursor.execute(
                        """
                            UPDATE AULAS
                            SET NOME=?,
                                ID_MODALIDADE=?,
                                ID_PROFESSOR=?,
                                DATA_AULA=?,
                                HORA_INICIO=?,
                                HORA_FIM=?,
                                CAPACIDADE=?,
                                LOCAL_AULA=?
                            WHERE ID_AULA=?
                        """,
                        (*valores, id_aula),
                    )
                else:
                    cursor = con.cursor()
                    cursor.execute(
                        """
                            INSERT INTO AULAS (NOME, ID_MODALIDADE, ID_PROFESSOR, DATA_AULA, HORA_INICIO, HORA_FIM, CAPACIDADE, LOCAL_AULA)
                            VALUES (?,?,?,?,?,?,?,?)
                        """,
                        valores,
                    )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash("Aula salva com sucesso!", "sucesso")
            return redirect(url_for("aulas"))
        except ValueError as e:
            flash(str(e), "erro")
        except fdb.DatabaseError as e:
            app.logger.warning("Validação de aula recusada: %s", e)
            flash(
                "Não foi possível salvar: confira modalidade ativa, professor, horários e capacidade.",
                "erro",
            )
    return render_template(
        "aula_form.html",
        item=item,
        modalidades=modos,
        professores=professores,
        titulo="Editar aula" if id_aula else "Criar aula",
    )


# Busca a aula e confere se o professor pode acessá-la
def obter_aula(con, id_aula):
    aula = consultar(con, AULAS_SQL + " WHERE A.ID_AULA=?", (id_aula,), True)
    if not aula:
        abort(404)
    if (
        g.usuario["tipo_usuario"] == "PERSONAL"
        and aula["id_professor"] != g.usuario["id_usuario"]
    ):
        abort(403)
    return aula


# Mostra os detalhes e as vagas da aula
@app.route("/aulas/<int:id_aula>")
def aula_detalhes(id_aula):
    con = conectar()
    try:
        aula = obter_aula(con, id_aula)
        inscricao = consultar(
            con,
            """
                SELECT *
                FROM INSCRICOES
                WHERE ID_AULA=?
                    AND ID_USUARIO=?
                    AND ATIVA=1
            """,
            (id_aula, g.usuario["id_usuario"]),
            True,
        )
        inscritos = (
            consultar(
                con,
                """
                    SELECT I.*,
                           U.NOME
                    FROM INSCRICOES I
                    JOIN USUARIOS U ON U.ID_USUARIO=I.ID_USUARIO
                    WHERE I.ID_AULA=?
                        AND I.ATIVA=1
                    ORDER BY U.NOME
                """,
                (id_aula,),
            )
            if g.usuario["tipo_usuario"] != "ALUNO"
            else []
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "aula_detalhes.html",
        aula=aula,
        inscricao=inscricao,
        inscritos=inscritos,
        hoje=date.today(),
    )


# Cancela a aula preservando os dados já registrados
@app.route("/aulas/<int:id_aula>/cancelar", methods=["GET", "POST"])
def aula_cancelar(id_aula):
    con = conectar()
    try:
        aula = obter_aula(con, id_aula)
        if request.method == "POST":
            cursor = con.cursor()
            cursor.execute(
                "UPDATE AULAS SET SITUACAO='CANCELADA' WHERE ID_AULA=?", (id_aula,)
            )
            flash("Aula cancelada. O histórico foi preservado.", "sucesso")
            con.commit()
            return redirect(url_for("aulas"))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "confirmar.html",
        titulo="Confirmar cancelamento da aula",
        mensagem=f"Cancelar a aula {aula['nome']}? O histórico será preservado.",
        voltar=url_for("aulas"),
        botao="Cancelar aula",
    )


# Inscreve o aluno somente quando houver vaga
@app.route("/aulas/<int:id_aula>/inscrever", methods=["POST"])
def inscrever(id_aula):
    try:
        con = conectar()
        try:
            consultar(
                con,
                "SELECT ID_AULA FROM AULAS WHERE ID_AULA=? WITH LOCK",
                (id_aula,),
                True,
            )
            aula = obter_aula(con, id_aula)
            if aula["situacao"] != "AGENDADA" or aula["data_aula"] < date.today():
                raise ValueError("Inscrição indisponível para esta aula.")
            if not consultar(
                con,
                """
                    SELECT ID_MODALIDADE
                    FROM MODALIDADES
                    WHERE ID_MODALIDADE=?
                        AND ATIVA=1
                """,
                (aula["id_modalidade"],),
                True,
            ):
                raise ValueError("Modalidade inativa. Inscrição indisponível.")
            inscricao = consultar(
                con,
                "SELECT * FROM INSCRICOES WHERE ID_AULA=? AND ID_USUARIO=?",
                (id_aula, g.usuario["id_usuario"]),
                True,
            )
            if inscricao and inscricao["ativa"]:
                raise ValueError("Você já está inscrito nesta aula.")
            if aula["inscritos"] >= aula["capacidade"]:
                raise ValueError("Aula lotada. Não há vagas disponíveis.")
            if inscricao:
                cursor = con.cursor()
                cursor.execute(
                    "UPDATE INSCRICOES SET ATIVA=1,PRESENTE=NULL WHERE ID_INSCRICAO=?",
                    (inscricao["id_inscricao"],),
                )
            else:
                cursor = con.cursor()
                cursor.execute(
                    "INSERT INTO INSCRICOES (ID_AULA,ID_USUARIO) VALUES (?,?)",
                    (id_aula, g.usuario["id_usuario"]),
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        flash("Inscrição realizada com sucesso!", "sucesso")
    except ValueError as e:
        flash(str(e), "erro")
    return redirect(url_for("minhas_aulas"))


# Lista as aulas em que o aluno está inscrito
@app.route("/minhas-aulas")
def minhas_aulas():
    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + " JOIN INSCRICOES IX ON IX.ID_AULA=A.ID_AULA WHERE IX.ID_USUARIO=? AND IX.ATIVA=1 ORDER BY A.DATA_AULA,A.HORA_INICIO",
            (g.usuario["id_usuario"],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("minhas_aulas.html", aulas=aulas)


# Cancela a inscrição e libera a vaga
@app.route("/inscricoes/<int:id_aula>/cancelar", methods=["GET", "POST"])
def cancelar_inscricao(id_aula):
    con = conectar()
    try:
        aula = obter_aula(con, id_aula)
        if not consultar(
            con,
            """
                SELECT ID_INSCRICAO
                FROM INSCRICOES
                WHERE ID_AULA=?
                    AND ID_USUARIO=?
                    AND ATIVA=1
            """,
            (id_aula, g.usuario["id_usuario"]),
            True,
        ):
            abort(404)
        if request.method == "POST":
            consultar(
                con,
                "SELECT ID_AULA FROM AULAS WHERE ID_AULA=? WITH LOCK",
                (id_aula,),
                True,
            )
            cursor = con.cursor()
            cursor.execute(
                "UPDATE INSCRICOES SET ATIVA=0 WHERE ID_AULA=? AND ID_USUARIO=?",
                (id_aula, g.usuario["id_usuario"]),
            )
            flash("Inscrição cancelada com sucesso!", "sucesso")
            con.commit()
            return redirect(url_for("minhas_aulas"))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        "confirmar.html",
        titulo="Confirmar cancelamento da inscrição",
        mensagem=f"Cancelar sua inscrição em {aula['nome']}? A vaga será liberada.",
        voltar=url_for("minhas_aulas"),
        botao="Confirmar cancelamento",
    )


# Registra a presença dos alunos na aula
@app.route("/chamada/<int:id_aula>", methods=["GET", "POST"])
def chamada(id_aula):
    con = conectar()
    try:
        aula = obter_aula(con, id_aula)
        inscritos = consultar(
            con,
            """
                SELECT I.*,
                       U.NOME
                FROM INSCRICOES I
                JOIN USUARIOS U ON U.ID_USUARIO=I.ID_USUARIO
                WHERE I.ID_AULA=?
                    AND I.ATIVA=1
                ORDER BY U.NOME
            """,
            (id_aula,),
        )
        if request.method == "POST":
            for i in inscritos:
                valor = request.form.get(f"presenca_{i['id_inscricao']}", "")
                cursor = con.cursor()
                cursor.execute(
                    "UPDATE INSCRICOES SET PRESENTE=? WHERE ID_INSCRICAO=?",
                    (int(valor) if valor in ("0", "1") else None, i["id_inscricao"]),
                )
            flash("Chamada salva com sucesso!", "sucesso")
            con.commit()
            return redirect(url_for("chamada", id_aula=id_aula))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template("chamada.html", aula=aula, inscritos=inscritos)


# Mostra uma página de erro sem abrir pop-ups
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(400)
def pagina_erro(erro):
    return (render_template("erro.html", erro=erro), erro.code)


# Mostra uma mensagem quando a operação no banco falha
@app.errorhandler(fdb.DatabaseError)
def erro_banco(erro):
    app.logger.exception("Erro no Firebird")
    mensagem = {
        "code": 500,
        "description": "Não foi possível concluir a operação no banco de dados. Confira o erro no terminal."
    }
    return render_template("erro.html", erro=mensagem), 500


# Inicia o sistema
if __name__ == "__main__":
    app.run()

## **OrganizaEquipe-API**

Este repositório contém a API do backend para a aplicação OrganizaEquipe, responsável por gerenciar equipes, organizações, escalas de trabalho e a disponibilidade dos membros. A API foi desenvolvida usando Python com o framework Django e Django REST Framework.

---

### **Funcionalidades**

A API oferece os seguintes recursos principais, refletindo a estrutura de dados do projeto:

- Autenticação e Usuários (`User`):

  - Gerencia o cadastro de novos usuários.

  - Fornece autenticação com tokens JWT (JSON Web Tokens) para acesso seguro.

  - Ao criar um novo usuário, ele é automaticamente adicionado ao grupo 'Users' com permissões padrão.

- Organizações (`Organization`):

  - Permite operações CRUD (Criar, Ler, Atualizar, Deletar) para organizações.

  - Gerencia a adição e remoção de membros e administradores de uma organização.

  - Filtra organizações por código de acesso ou por membros.

- Equipes (`Team`):

  - Permite operações CRUD para equipes.

  - Gerencia a adição e remoção de membros e administradores de uma equipe.

  - Oferece uma funcionalidade para listar membros disponíveis em uma data específica, verificando indisponibilidade e participações em outras escalas.

  - Filtra equipes por código de acesso ou por membros.

- Funções (`Role`):

  - Permite operações CRUD para as funções (cargos) dentro de uma equipe.

- Escalas (`Schedule`):

  - Criação e gerenciamento de escalas de trabalho com data, hora e equipe associada.

  - Gerenciamento de participações em escalas, incluindo a confirmação de presença de cada usuário.

- Indisponibilidade (`Unavailability`):

  - Os usuários podem registrar períodos de indisponibilidade para que não sejam escalados.

- Convites (`Invitation`) e Solicitações (`Request`):

  - A API gerencia convites para entrar em equipes e organizações.

  - Lida com solicitações de usuários que desejam entrar em uma equipe ou organização por meio de um código de acesso.

---

### **Tecnologias Utilizadas**

- Python 3

- Django

- Django REST Framework

- Django REST Framework SimpleJWT para autenticação e renovação de token.

- drf-spectacular para geração de documentação da API (compatível com OpenAPI 3).

- dj-database-url para configuração simplificada do banco de dados.

- psycopg2-binary para conexão com PostgreSQL.

- whitenoise para servir arquivos estáticos em produção.

---

### **Instalação e Execução Local**

Siga os passos abaixo para configurar e rodar o projeto localmente:

1. Clone o repositório:

    ```bash
    git clone https://github.com/martinsglucas/OrganizaEquipe-API.git

    cd OrganizaEquipe-API
    ```

2. Crie e ative um ambiente virtual:

    ```bash
    python -m venv venv
    source venv/bin/activate  # Para Linux/macOS
    # venv\Scripts\activate  # Para Windows
    ```

3. Instale as dependências:

    ```bash
    pip install -r requirements.txt
    ```

4. Configure o banco de dados: O projeto usa o `db.sqlite3` por padrão, mas pode ser configurado para usar PostgreSQL ou outro banco de dados através da variável de ambiente `DATABASE_URL`.

5. Execute as migrações:

    ```bash
    python manaage.py migrate
    ```

6. Crie um superusuário (opcional, mas recomendado):

    ```bash
    python manage.py createsuperuser
    ```

7. Inicie o servidor de desenvolvimento:

    ```bash
    python manage.py runserver
    ```

    A API estará disponível em http://localhost:8000/.

---

### **Documentação da API**

A documentação da API pode ser acessada em:

Swagger UI: http://localhost:8000/api/swagger/

Redoc: http://localhost:8000/api/redoc/
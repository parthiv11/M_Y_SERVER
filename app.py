from flask import Flask, request, jsonify
import jwt
from functools import wraps
import mindsdb_sdk
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
PROJECT_NAME = 'm_y_ai' 
MODEL_NAME = 'mindyourai'

def get_or_create_project(server, project_name=PROJECT_NAME):
    try:
        return server.get_project(project_name) 
    except:
        return server.create_project(project_name)


def get_or_create_model(key, project,server, model_name=MODEL_NAME):
    try:
        return  project.get_model(MODEL_NAME) 
    except:
        return project.create_model(
        name = MODEL_NAME,
        predict = 'answer',
        engine=server.ml_engines.openai,
        prompt_template = 'Context: {"{{context}}"}. Question: {"{{question}}"}. Answer:',
        max_tokens = 3900,
        temperature = 0.6,
        api_key= key
    )
    


def verify_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token not provided'}), 403

        try:
            decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user = decoded
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return func(decoded, *args, **kwargs)

    return wrapper

# Authentication endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    key = data.get('key')
    try:
        server = mindsdb_sdk.connect(login=email, password=password)
        project = get_or_create_project(server=server)
        
        my_model = get_or_create_model(key=key,project=project,server=server)
        token = jwt.encode({'email': email, 'password': password}, app.config['SECRET_KEY'], algorithm=os.getenv('ALGORITHM'))
        return jsonify({'token': token})

    except Exception as e:

        return jsonify({'error': str(e)}), 401


# Protected endpoint example
@app.route('/getPrediction', methods=['POST'])
@verify_token
def get_prediction(decoded):
    data = request.get_json()
    query_type = data['query_type']
    inputs = data['inputs']
    server = mindsdb_sdk.connect(login=decoded.get("email"), password=decoded.get("password"))
    if query_type == 'default':
        sql_query = f"""
            SELECT answer
            FROM {PROJECT_NAME}.{MODEL_NAME}
            WHERE question='{inputs['question']}'
            AND context='{inputs['context']}';
        """

    elif query_type == 'linkedin':
        inputs['post'] = inputs['post'].replace("'", '"')
        sql_query = f"""
            SELECT answer
            FROM {PROJECT_NAME}.{MODEL_NAME}
            WHERE post='{inputs['post']}'
            AND prompt='{inputs['prompt']}'
            USING
                prompt_template = 'Generate short and nice comment for me LinkedIn comment for post:{"{{post}}"} as described by me in prompt: {"{{prompt}}"}. Answer:',
                max_tokens = 2900,
                temperature = 0.6;
        """

    elif query_type == 'gmail':
        inputs['last_reply'] = inputs['last_reply'].replace("'", '"')
        sql_query = f"""
            SELECT answer
            FROM {PROJECT_NAME}.{MODEL_NAME}
            WHERE mail='{inputs['last_reply']}'
            AND prompt='{inputs['prompt']}'
            USING
                prompt_template = 'Generate short and nice gmail reply for mail received by me:{"{{mail}}"} as described by me in prompt: {"{{prompt}}"}. Answer:',
                max_tokens = 2900,
                temperature = 0.6;
        """

    elif query_type == 'gmail_compose':
        sql_query = f"""
            SELECT answer
            FROM {PROJECT_NAME}.{MODEL_NAME}
            WHERE prompt='{inputs['prompt']}'
            USING
                prompt_template = 'Draft a nice email as described in prompt: {"{{prompt}}"}. Answer:',
                max_tokens = 2900,
                temperature = 0.6;
        """

    else:
        raise ValueError('Invalid query type')

    try:
        result = server.query(sql_query).fetch()
        return jsonify({'prediction': result[0][0] if result else None})
    except Exception as e:
        return jsonify({'error': str(e)})


# ADD Update key function     


if __name__ == '__main__':
    app.run()

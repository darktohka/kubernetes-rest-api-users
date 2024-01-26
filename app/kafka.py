from .app import kafka_uri, kafka_username, kafka_password
from .identity import set_jwt_secret
from kafka import KafkaConsumer, KafkaProducer
import binascii, threading, os
import msgpack

config = {
    'bootstrap_servers': [kafka_uri],
    'security_protocol': 'SASL_PLAINTEXT',
    'sasl_mechanism': 'SCRAM-SHA-256',
    'sasl_plain_username': kafka_username,
    'sasl_plain_password': kafka_password,
    'api_version': (1, 0, 0)
}

print('Config:', config)

def create_consumer(*args, **kwargs):
    kwargs.update(config)
    kwargs['value_deserializer'] = msgpack.unpackb
    return KafkaConsumer(*args, **kwargs)

def create_producer(*args, **kwargs):
    kwargs.update(config)
    kwargs['value_serializer'] = msgpack.dumps
    return KafkaProducer(*args, **kwargs)

jwt_producer = create_producer()

def register_kafka_listener(*args, **kwargs):
    listener = kwargs.pop('listener')

    def poll():
        consumer = create_consumer(*args, **kwargs)
        consumer.poll(timeout_ms=6000)

        for msg in consumer:
            listener(msg)

    thread = threading.Thread(target=poll)
    thread.start()

def rotate_jwt():
    print('Rotating JWT...')
    secret = binascii.hexlify(os.urandom(16)).decode('utf-8')
    set_jwt_secret(secret)

    jwt_producer.send('jwt-rotated', {'jwt': secret})
    jwt_producer.flush()

def jwt_rotated(message):
    data = message.value
    secret = data['jwt']
    set_jwt_secret(secret)

register_kafka_listener('jwt-rotated', auto_offset_reset='earliest', listener=jwt_rotated)
rotate_jwt()

from .app import kafka_uri, kafka_username, kafka_password
from .identity import set_jwt_secret
from kafka import KafkaConsumer, KafkaProducer
import binascii, threading, os

config = {
    'bootstrap_servers': [kafka_uri],
    'sasl_mechanism': 'SCRAM-SHA-256',
    'sasl_plain_username': kafka_username,
    'sasl_plain_password': kafka_password
}

def create_consumer(*args, **kwargs):
    kwargs.update(config)
    return KafkaConsumer(*args, **kwargs)

def create_producer(*args, **kwargs):
    kwargs.update(config)
    return KafkaProducer(*args, **kwargs)

jwt_producer = create_producer('jwt-rotated', auto_offset_reset='latest')

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
    jwt_producer.send('jwt-rotated', binascii.hexlify(os.urandom(16)))
    jwt_producer.flush()

def jwt_rotated(data):
    secret = data.decode('utf-8')

    print('JWT rotated:', secret)
    set_jwt_secret(secret)

register_kafka_listener('jwt-rotated', group_id='jwt-rotation-consumers', auto_offset_reset='earliest', listener=jwt_rotated)
rotate_jwt()

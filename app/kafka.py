from .app import kafka_uri, kafka_username, kafka_password
from kafka import KafkaConsumer, KafkaProducer
import threading
import msgpack

config = {
    'bootstrap_servers': [kafka_uri],
    'security_protocol': 'SASL_PLAINTEXT',
    'sasl_mechanism': 'SCRAM-SHA-256',
    'sasl_plain_username': kafka_username,
    'sasl_plain_password': kafka_password,
    'api_version': (1, 0, 0)
}

def create_consumer(*args, **kwargs):
    kwargs.update(config)
    kwargs['value_deserializer'] = msgpack.unpackb
    return KafkaConsumer(*args, **kwargs)

def create_producer(*args, **kwargs):
    kwargs.update(config)
    kwargs['value_serializer'] = msgpack.dumps
    return KafkaProducer(*args, **kwargs)

def register_kafka_listener(*args, **kwargs):
    listener = kwargs.pop('listener')

    def poll():
        consumer = create_consumer(*args, **kwargs)

        for msg in consumer:
            listener(msg)

    thread = threading.Thread(target=poll)
    thread.start()

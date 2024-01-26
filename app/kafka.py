from .app import kafka_uri, kafka_username, kafka_password
from .identity import set_jwt_secret
from kafka import KafkaConsumer, KafkaProducer
from kafka.structs import TopicPartition
import binascii, threading, os
import msgpack, time

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

jwt_producer = create_producer()

def register_kafka_listener(*args, **kwargs):
    listener = kwargs.pop('listener')

    def poll():
        consumer = create_consumer(*args, **kwargs)

        while True:
            consumer.poll(timeout_ms=6000)

            print('Polling consumer...')

            for msg in consumer:
                print('Message found:', msg)
                listener(msg)

            print('Done.')

        time.sleep(0.1)

    thread = threading.Thread(target=poll)
    thread.start()

def rotate_jwt():
    print('Rotating JWT...')
    secret = binascii.hexlify(os.urandom(16)).decode('utf-8')
    set_jwt_secret(secret)

    jwt_producer.send('jwt-rotated', {'jwt': secret})
    jwt_producer.flush()

def rotate_jwt_if_necessary():
    consumer = create_consumer('jwt-rotated', auto_offset_reset='earliest')
    partition_number = next(iter(consumer.partitions_for_topic('jwt-rotated')))
    partition = TopicPartition('jwt-rotated', partition_number)

    consumer.seek_to_end(partition)
    end_position = consumer.position(partition)

    consumer.seek_to_beginning(partition)
    start_position = consumer.position(partition)

    print('Start:', start_position)
    print('End:', end_position)

    if start_position == end_position:
        rotate_jwt()
    else:
        print('JWT rotation not required.')

def jwt_rotated(message):
    data = message.value
    secret = data['jwt']
    set_jwt_secret(secret)

rotate_jwt_if_necessary()
register_kafka_listener('jwt-rotated', enable_auto_commit=False, auto_offset_reset='earliest', listener=jwt_rotated)

import src.shared.kafka.topics as topics
from confluent_kafka.admin import AdminClient, NewTopic
from src.shared.config import settings

TOPICS = [
    (topics.TOPIC_INGRESS, 1, 1),
    (topics.TOPIC_JOBS, 1, 1),
    (topics.TOPIC_SEGMENTS, 1, 1),
    (topics.TOPIC_RETRY_30S, 1, 1),
    (topics.TOPIC_RETRY_5M, 1, 1),
    (topics.TOPIC_DLQ, 1, 1),
]


def main():
    bootstrap = settings.KAFKA_BOOTSTRAP_SERVERS
    admin = AdminClient({"bootstrap.servers": bootstrap})
    new_topics = [NewTopic(topic, num_partitions, replication_factor) for topic, num_partitions, replication_factor in TOPICS]

    fs = admin.create_topics(new_topics)
    for topic, f in fs.items():
        try:
            f.result()
            print(f"Created topic {topic}")
        except Exception as e:
            print(f"Failed to create topic {topic}: {e}")


if __name__ == "__main__":
    main()

CREATE DATABASE IF NOT EXISTS wanguard;

CREATE TABLE IF NOT EXISTS wanguard.raw_flows
(
    Time DateTime,
    Date Date DEFAULT toDate(Time),
    SensorID UInt16,
    Protocol LowCardinality(String),
    SrcIP IPv4,
    DstIP IPv4,
    SrcPort UInt16,
    DstPort UInt16,
    TCPFlags LowCardinality(String),
    Packets UInt64,
    Bytes UInt64
)
ENGINE = MergeTree()
PARTITION BY Date
ORDER BY (Time, DstIP, SrcIP)
TTL Date + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS wanguard.top_dst_ips_mv
ENGINE = SummingMergeTree()
PARTITION BY Date
ORDER BY (Time, DstIP)
AS
SELECT
    Date,
    toStartOfMinute(Time) AS Time,
    DstIP,
    sum(Packets) AS TotalPackets,
    sum(Bytes) AS TotalBytes
FROM wanguard.raw_flows
GROUP BY
    Date,
    Time,
    DstIP;

CREATE MATERIALIZED VIEW IF NOT EXISTS wanguard.top_src_ips_mv
ENGINE = SummingMergeTree()
PARTITION BY Date
ORDER BY (Time, SrcIP)
AS
SELECT
    Date,
    toStartOfMinute(Time) AS Time,
    SrcIP,
    sum(Packets) AS TotalPackets,
    sum(Bytes) AS TotalBytes
FROM wanguard.raw_flows
GROUP BY
    Date,
    Time,
    SrcIP;

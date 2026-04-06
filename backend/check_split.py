import sqlite3
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# 查找最近的数据集统计信息
cursor.execute("""
    SELECT ds.dataset_id, d.name, ds.split_distribution, ds.scan_status
    FROM datasetstatistics ds
    JOIN dataset d ON ds.dataset_id = d.id
    ORDER BY ds.last_scan_time DESC LIMIT 5
""")

rows = cursor.fetchall()
print("最近的数据集统计信息:")
for row in rows:
    print(f"  数据集: {row[1]}")
    print(f"  ID: {row[0][:8]}...")
    print(f"  split_distribution: {row[2]}")
    print(f"  status: {row[3]}")
    print()

conn.close()

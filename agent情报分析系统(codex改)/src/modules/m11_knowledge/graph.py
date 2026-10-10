"""
M11 知识图谱模块
支持实体解析、关系发现、图谱查询
"""

import json
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import uuid
import sqlite3


@dataclass
class Entity:
    """实体"""
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: str = "general"  # person, organization, event, concept, location
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Relation:
    """关系"""
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: str = "related_to"  # causes, correlates, contradicts, supports
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GraphPath:
    """图路径"""
    nodes: List[Entity]
    edges: List[Relation]
    total_weight: float


class KnowledgeGraph:
    """
    知识图谱
    
    支持：
    - 实体管理（增删改查）
    - 关系管理
    - 路径查询
    - 子图提取
    - 实体解析（去重合并）
    """
    
    def __init__(self, db_path: str = "data/knowledge_graph.db"):
        self.db_path = db_path
        self._entities: Dict[str, Entity] = {}
        self._relations: List[Relation] = []
        self._adjacency: Dict[str, List[Tuple[str, Relation]]] = defaultdict(list)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                properties TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                relation_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                properties TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES entities(entity_id),
                FOREIGN KEY(target_id) REFERENCES entities(entity_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON relations(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_target ON relations(target_id)")
        conn.commit()
        conn.close()
    
    def add_entity(self, entity: Entity) -> str:
        """添加实体"""
        self._entities[entity.entity_id] = entity
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO entities
            (entity_id, name, entity_type, properties, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            entity.entity_id, entity.name, entity.entity_type,
            json.dumps(entity.properties, ensure_ascii=False),
            entity.created_at.isoformat()
        ))
        conn.commit()
        conn.close()
        return entity.entity_id
    
    def add_relation(self, relation: Relation) -> str:
        """添加关系"""
        self._relations.append(relation)
        self._adjacency[relation.source_id].append((relation.target_id, relation))
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO relations
            (relation_id, source_id, target_id, relation_type, weight, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            relation.relation_id, relation.source_id, relation.target_id,
            relation.relation_type, relation.weight,
            json.dumps(relation.properties, ensure_ascii=False),
            relation.created_at.isoformat()
        ))
        conn.commit()
        conn.close()
        return relation.relation_id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        if entity_id in self._entities:
            return self._entities[entity_id]
        
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        conn.close()
        
        if row:
            entity = Entity(
                entity_id=row[0], name=row[1], entity_type=row[2],
                properties=json.loads(row[3]) if row[3] else {},
                created_at=datetime.fromisoformat(row[4])
            )
            self._entities[entity_id] = entity
            return entity
        return None
    
    def find_entities(self, name: Optional[str] = None, 
                     entity_type: Optional[str] = None) -> List[Entity]:
        """查找实体"""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM entities WHERE 1=1"
        params = []
        
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        
        cursor = conn.execute(query, params)
        entities = []
        for row in cursor:
            entity = Entity(
                entity_id=row[0], name=row[1], entity_type=row[2],
                properties=json.loads(row[3]) if row[3] else {},
                created_at=datetime.fromisoformat(row[4])
            )
            entities.append(entity)
        conn.close()
        return entities
    
    def get_neighbors(self, entity_id: str, max_depth: int = 1) -> List[Entity]:
        """获取邻居实体"""
        visited: Set[str] = set()
        queue = [(entity_id, 0)]
        neighbors = []
        
        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            
            if current_id != entity_id:
                entity = self.get_entity(current_id)
                if entity:
                    neighbors.append(entity)
            
            for target_id, _ in self._adjacency.get(current_id, []):
                if target_id not in visited:
                    queue.append((target_id, depth + 1))
        
        return neighbors
    
    def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> Optional[GraphPath]:
        """查找两个实体之间的路径（BFS）"""
        visited: Set[str] = set()
        queue = [(source_id, [])]
        
        while queue:
            current_id, path = queue.pop(0)
            if current_id in visited or len(path) > max_depth:
                continue
            visited.add(current_id)
            
            if current_id == target_id:
                nodes = [self.get_entity(nid) for nid in [source_id] + [p[0] for p in path] if self.get_entity(nid)]
                edges = [p[1] for p in path]
                return GraphPath(nodes=nodes, edges=edges, total_weight=sum(r.weight for r in edges))
            
            for target, relation in self._adjacency.get(current_id, []):
                if target not in visited:
                    queue.append((target, path + [(target, relation)]))
        
        return None
    
    def resolve_entity(self, new_entity: Entity, similarity_threshold: float = 0.8) -> str:
        """实体解析（去重合并）"""
        existing = self.find_entities(name=new_entity.name, entity_type=new_entity.entity_type)
        
        for entity in existing:
            if entity.name == new_entity.name:
                # 合并属性
                entity.properties.update(new_entity.properties)
                self.add_entity(entity)
                return entity.entity_id
        
        return self.add_entity(new_entity)
    
    def get_subgraph(self, entity_ids: List[str]) -> Dict[str, Any]:
        """提取子图"""
        nodes = [self.get_entity(eid) for eid in entity_ids]
        nodes = [n for n in nodes if n]
        
        edges = [
            r for r in self._relations
            if r.source_id in entity_ids and r.target_id in entity_ids
        ]
        
        return {
            "nodes": [
                {"id": n.entity_id, "name": n.name, "type": n.entity_type, "properties": n.properties}
                for n in nodes
            ],
            "edges": [
                {"source": e.source_id, "target": e.target_id, "type": e.relation_type, "weight": e.weight}
                for e in edges
            ]
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """图谱统计"""
        conn = sqlite3.connect(self.db_path)
        entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        
        type_counts = {}
        for row in conn.execute("SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"):
            type_counts[row[0]] = row[1]
        
        conn.close()
        
        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "entity_types": type_counts
        }

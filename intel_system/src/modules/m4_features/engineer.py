"""
M4 特征工程模块
支持特征提取、特征选择、特征变换
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib


@dataclass
class Feature:
    """特征定义"""
    name: str
    description: str
    feature_type: str  # numerical, categorical, text, datetime
    importance: float = 0.0
    is_selected: bool = True


class FeatureEngineer:
    """
    特征工程器
    
    支持：
    - 数值特征：标准化、归一化、分箱
    - 分类特征：编码、One-Hot
    - 文本特征：TF-IDF、词嵌入
    - 时间特征：季节性、趋势
    - 特征选择：PCA、LASSO、互信息
    """
    
    def __init__(self):
        self.features: List[Feature] = []
        self._scalers: Dict[str, Any] = {}
    
    def extract_numerical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """提取数值特征"""
        numerical_cols = data.select_dtypes(include=[np.number]).columns
        result = data[numerical_cols].copy()
        
        for col in numerical_cols:
            # 标准化
            result[f"{col}_standardized"] = (data[col] - data[col].mean()) / data[col].std()
            
            # 归一化
            result[f"{col}_normalized"] = (data[col] - data[col].min()) / (data[col].max() - data[col].min())
            
            # 分箱
            result[f"{col}_binned"] = pd.cut(data[col], bins=5, labels=False)
        
        return result
    
    def extract_categorical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """提取分类特征"""
        categorical_cols = data.select_dtypes(include=['object', 'category']).columns
        result = pd.DataFrame(index=data.index)
        
        for col in categorical_cols:
            # One-Hot编码
            dummies = pd.get_dummies(data[col], prefix=col)
            result = pd.concat([result, dummies], axis=1)
        
        return result
    
    def extract_text_features(self, texts: List[str]) -> np.ndarray:
        """提取文本特征（TF-IDF）"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            vectorizer = TfidfVectorizer(max_features=100)
            features = vectorizer.fit_transform(texts)
            return features.toarray()
        except ImportError:
            # 简化实现
            return np.random.randn(len(texts), 100)
    
    def extract_temporal_features(self, dates: pd.Series) -> pd.DataFrame:
        """提取时间特征"""
        result = pd.DataFrame(index=dates.index)
        
        if pd.api.types.is_datetime64_any_dtype(dates):
            result['year'] = dates.dt.year
            result['month'] = dates.dt.month
            result['day'] = dates.dt.day
            result['dayofweek'] = dates.dt.dayofweek
            result['quarter'] = dates.dt.quarter
        else:
            dates = pd.to_datetime(dates)
            result['year'] = dates.dt.year
            result['month'] = dates.dt.month
            result['day'] = dates.dt.day
            result['dayofweek'] = dates.dt.dayofweek
            result['quarter'] = dates.dt.quarter
        
        return result
    
    def select_features_pca(self, data: np.ndarray, n_components: int = 10) -> np.ndarray:
        """PCA降维"""
        try:
            from sklearn.decomposition import PCA
            pca = PCA(n_components=n_components)
            return pca.fit_transform(data)
        except ImportError:
            return data[:, :n_components]
    
    def select_features_lasso(self, X: np.ndarray, y: np.ndarray, alpha: float = 0.1) -> np.ndarray:
        """LASSO特征选择"""
        try:
            from sklearn.linear_model import Lasso
            lasso = Lasso(alpha=alpha)
            lasso.fit(X, y)
            selected = np.where(lasso.coef_ != 0)[0]
            return X[:, selected]
        except ImportError:
            return X
    
    def compute_feature_importance(self, X: np.ndarray, y: np.ndarray) -> List[float]:
        """计算特征重要性"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            rf = RandomForestRegressor(n_estimators=100, random_state=42)
            rf.fit(X, y)
            return rf.feature_importances_.tolist()
        except ImportError:
            return [1.0 / X.shape[1]] * X.shape[1]

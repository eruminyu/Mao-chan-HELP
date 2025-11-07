# common_utils.py
import sys
import os
import json

def get_datafile_path(relative_path):
    """
    실행 파일(exe) 또는 스크립트 위치를 기준으로 데이터 파일의 절대 경로를 반환합니다.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 등으로 번들된 경우 (exe)
        base_path = os.path.dirname(sys.executable)
    else:
        # 일반 Python 스크립트로 실행된 경우
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

GAMEDATA_FILE = get_datafile_path('gamedata.json')
USERDECKS_FILE = get_datafile_path('user_decks.json')

STYLE_TYPES = [
    ("main1", "메인유파1"), ("main2", "메인유파2"), ("main_common", "메인공용"),
    ("support1", "지원유파1"), ("support2", "지원유파2"), ("support_common", "지원공용")
]

class DataParser:
    def __init__(self):
        self.data = {}
        self.load_data_files()

    def load_data_files(self):
        files_to_load = ["HitDamage", "EffectValue", "OnceAdditionalAttributeValue", "BuffValue", "ScriptParameterValue"]
        for filename in files_to_load:
            try:
                path = get_datafile_path(f'{filename}.json')
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content: self.data[filename] = json.loads(content)
                    else: self.data[filename] = {}
            except (FileNotFoundError, json.JSONDecodeError): self.data[filename] = {}

    def parse_param(self, param_str):
        parts = param_str.split(',')
        if len(parts) < 3: return None
        table_name, record_id = parts[0], parts[2]
        if table_name not in self.data or record_id not in self.data[table_name]: return None
        record = self.data[table_name][record_id]; stat_name = f"{table_name} 효과"; value = 0.0
        try:
            if table_name == "HitDamage": stat_name = "스킬 피해 %"; value = float(record.get("SkillPercentAmend", [0])[0]) / 10000.0
            elif table_name in ["EffectValue", "BuffValue"]: stat_name = "효과값 %"; value = float(record.get("EffectTypeParam1", "0.0")) * 100.0
            elif table_name == "OnceAdditionalAttributeValue": stat_name = "추가 스탯 %"; value = float(record.get("Value1", 0)) / 100.0
            elif table_name == "ScriptParameterValue": stat_name = "특수 조건 값"; value = float(record.get("CommonData", 0)) / 10000.0
            else: return None
        except (ValueError, TypeError): return None
        return {"type": stat_name, "value": value}
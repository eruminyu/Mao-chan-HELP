# tracker.py (v4.8 - 메시지 중앙 정렬 및 한글 필터링)
import sys
import json
import os
import time
import re
import pygetwindow as gw
import pytesseract
from PIL import Image, ImageGrab, ImageOps
from PIL.ImageQt import ImageQt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QFormLayout,
                             QMessageBox, QListWidget, QListWidgetItem, QDialog)
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QBrush, QPen

# --- 경로 설정 함수 ---
# (v4.7과 동일)
def get_bundled_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
def get_datafile_path(relative_path):
    if getattr(sys, 'frozen', False): base_path = os.path.dirname(sys.executable)
    else: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
# --------------------

# --- 설정 ---
# (v4.7과 동일)
YOUR_TESSERACT_PATH = get_bundled_path(os.path.join('tesseract_bundle', 'tesseract.exe'))
CONFIG_FILE = get_datafile_path('config.json')
GAMEDATA_FILE = get_datafile_path('gamedata.json')
USERDECKS_FILE = get_datafile_path('user_decks.json')

# --- Tesseract 검사 ---
# (v4.7과 동일)
try:
    pytesseract.pytesseract.tesseract_cmd = YOUR_TESSERACT_PATH
    pytesseract.get_tesseract_version()
except Exception as e:
    app_temp = QApplication(sys.argv); QMessageBox.critical(None, "치명적 오류", f"Tesseract 초기화 오류: {e}\ntesseract_bundle 폴더나 경로를 확인하세요."); sys.exit()
# --------------------

# --- 1단계: 게임 창 설정 ---
# (GameWindowSetupDialog 클래스 코드는 v4.7과 동일)
class GameWindowSetupDialog(QDialog):
    game_window_selected = pyqtSignal(str)
    def __init__(self, parent=None): super().__init__(parent); self.setWindowTitle("1단계: 게임 창 설정"); self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint); self.setModal(True); self.setGeometry(400, 400, 500, 400); layout = QVBoxLayout(); layout.addWidget(QLabel("현재 실행 중인 프로그램 목록입니다.\n'스텔라 소라' 게임을 선택하고 [확인]을 누르세요.")); self.list_widget = QListWidget(); layout.addWidget(self.list_widget); button_layout = QHBoxLayout(); self.refresh_btn = QPushButton("새로고침"); self.refresh_btn.clicked.connect(self.populate_windows); self.confirm_btn = QPushButton("확인"); self.confirm_btn.clicked.connect(self.on_confirm); button_layout.addWidget(self.refresh_btn); button_layout.addWidget(self.confirm_btn); layout.addLayout(button_layout); self.setLayout(layout); self.populate_windows()
    def populate_windows(self): self.list_widget.clear(); [self.list_widget.addItem(QListWidgetItem(title)) for title in gw.getAllTitles() if title]
    def on_confirm(self): selected_item = self.list_widget.currentItem(); (self.game_window_selected.emit(selected_item.text()), self.accept()) if selected_item else QMessageBox.warning(self, "알림", "목록에서 게임 창을 선택하세요.")
    def closeEvent(self, event):
        if not self.list_widget.currentItem(): QMessageBox.warning(self, "알림", "게임 창을 선택해야 설정이 완료됩니다."); event.ignore()
        else: reply = QMessageBox.question(self, "종료 확인", "설정이 완료되지 않았습니다. 종료하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); self.reject() if reply == QMessageBox.StandardButton.Yes else event.ignore()

# --- 2단계: 캡처 영역 설정 ---
class SetupWindow(QWidget):
    coordinates_saved = pyqtSignal(dict); cancelled = pyqtSignal()
    def __init__(self, screenshot):
        # (v4.7과 동일)
        super().__init__()
        try:
            self.screenshot = screenshot
            if isinstance(screenshot, Image.Image): self.qt_image = ImageQt(self.screenshot); self.pixmap = QPixmap.fromImage(self.qt_image)
            else: self.pixmap = QPixmap(); print("오류: 스크린샷 객체 타입 오류")
            self.current_step = 1; self.boxes = {}; self.begin_pos = QPoint(); self.end_pos = QPoint(); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint); self.showFullScreen();
            if not self.isFullScreen(): print("경고: 전체 화면 모드 진입 실패."); self.showMaximized()
            self.setWindowOpacity(0.7); self.setMouseTracking(True); print("SetupWindow 생성 및 표시 성공")
        except Exception as e: print(f"SetupWindow 생성 오류: {e}"); QMessageBox.critical(None, "오류", f"캡처 설정 창 생성 실패: {e}\n프로그램을 다시 시작해주세요."); QTimer.singleShot(100, self.cancelled.emit); QTimer.singleShot(150, self.close)

    # --- (★수정된 부분★) ---
    def paintEvent(self, event):
        try:
            painter = QPainter(self);
            painter.drawPixmap(self.rect(), self.pixmap);

            instruction_font = QFont('Malgun Gothic', 20, QFont.Weight.Bold)
            painter.setFont(instruction_font)
            text = f"[{self.current_step}/3] 번째 잠재력 영역을 드래그하세요. (취소는 [ESC] 키)"

            fm = painter.fontMetrics()
            # 텍스트가 차지할 예상 크기 계산 (화면 너비 제한 없이)
            text_bounding_rect = fm.boundingRect(text) # QRect 반환

            # 배경 상자의 너비/높이 설정 (텍스트 크기 + 여백)
            bg_width = text_bounding_rect.width() + 40 # 좌우 여백 20씩
            bg_height = text_bounding_rect.height() + 10 # 상하 여백 5씩
            # 배경 상자의 위치 계산 (화면 상단 중앙)
            bg_x = (self.width() - bg_width) // 2
            bg_y = 20 # 화면 상단에서 20px 아래

            draw_rect = QRect(bg_x, bg_y, bg_width, bg_height)

            # 반투명 검은색 배경 그리기
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(draw_rect)

            # 빨간색 텍스트 그리기 (배경 상자 안에서 중앙 정렬)
            painter.setPen(QColor(255, 0, 0))
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, text) # 수직/수평 모두 중앙

            # 현재 드래그 영역 그리기
            if not self.begin_pos.isNull() and not self.end_pos.isNull():
                rect = QRect(self.begin_pos, self.end_pos).normalized();
                green_pen = QPen(QColor(0, 255, 0, 200))
                painter.setPen(green_pen)
                painter.setBrush(QColor(0, 255, 0, 50));
                painter.drawRect(rect)
            painter.end()
        except Exception as e:
             print(f"paintEvent 오류: {e}")
    # ------------------------

    def mousePressEvent(self, event): self.begin_pos = event.pos(); self.end_pos = event.pos(); self.update()
    def mouseMoveEvent(self, event):
        if not self.begin_pos.isNull(): self.end_pos = event.pos(); self.update()
    def mouseReleaseEvent(self, event):
        # (v4.7과 동일)
        if self.begin_pos.isNull(): return
        self.end_pos = event.pos(); rect = QRect(self.begin_pos, self.end_pos).normalized()
        if rect.width() < 10 or rect.height() < 10: self.begin_pos = QPoint(); self.end_pos = QPoint(); self.update(); return
        box_coords = (rect.left(), rect.top(), rect.right(), rect.bottom()); self.boxes[f"box{self.current_step}"] = box_coords
        self.current_step += 1; self.begin_pos = QPoint(); self.end_pos = QPoint()
        if self.current_step > 3: self.coordinates_saved.emit(self.boxes); self.close()
        else: self.update()
    def keyPressEvent(self, event):
        # (v4.7과 동일)
        if event.key() == Qt.Key.Key_Escape: self.cancelled.emit(); self.close()

# --- 3. 메인 트래커 앱 ---
class TrackerApp(QWidget):
    # (v4.7과 동일)
    def __init__(self): super().__init__(); self.game_data = {}; self.user_decks = {}; self.coordinates = {}; self.game_window_title = ""; self.setup_window = None; self.load_all_data(); self.initUI()
    def load_all_data(self):
        try:
            with open(GAMEDATA_FILE, 'r', encoding='utf-8') as f: self.game_data = json.load(f)
            with open(USERDECKS_FILE, 'r', encoding='utf-8') as f: self.user_decks = json.load(f)
        except FileNotFoundError as e: self.show_error_message(f"데이터 파일({e.filename})을 찾을 수 없습니다.")
        except Exception as e: self.show_error_message(f"데이터 로드 오류: {e}")
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: config_data = json.load(f)
                self.coordinates = config_data.get("coordinates", {}); self.game_window_title = config_data.get("game_window_title", "")
                if 'box1' in self.coordinates and 'box2' in self.coordinates and 'box3' in self.coordinates and self.game_window_title: self.run_button.setEnabled(True); self.config_status_label.setText(f"설정 완료 (게임: {self.game_window_title[:20]}...)"); self.config_status_label.setStyleSheet("color: green;"); return True
                else: raise ValueError("설정 파일 데이터가 불완전합니다.")
            except Exception as e: self.show_error_message(f"config.json 읽기 오류: {e}\n설정을 다시 진행합니다.")
        self.run_button.setEnabled(False); self.config_status_label.setText("상태: 캡처 영역/게임 창 설정 필요"); self.config_status_label.setStyleSheet("color: red;"); return False
    def initUI(self):
        deck_select_layout = QHBoxLayout(); self.deck_select_label = QLabel("적용할 덱:"); self.deck_select_combo = QComboBox(self);
        if self.user_decks: self.deck_select_combo.addItems(self.user_decks.keys())
        else: self.deck_select_combo.addItem("불러온 덱 없음")
        self.deck_select_combo.textActivated.connect(self.on_deck_changed); deck_select_layout.addWidget(self.deck_select_label); deck_select_layout.addWidget(self.deck_select_combo); self.run_button = QPushButton("현재 잠재력 확인 (F10)", self); self.run_button.setShortcut("F10"); self.run_button.clicked.connect(self.run_ocr_check); self.run_button.setStyleSheet("font-size: 16px; padding: 10px;"); self.setup_button = QPushButton("설정 다시하기", self); self.setup_button.clicked.connect(self.run_full_setup); self.config_status_label = QLabel("상태: 로딩 중..."); setup_layout = QHBoxLayout(); setup_layout.addWidget(self.setup_button); setup_layout.addWidget(self.config_status_label); self.result_layout = QFormLayout(); self.result_label_1 = QLabel("..."); self.result_label_2 = QLabel("..."); self.result_label_3 = QLabel("..."); self.result_label_1.setStyleSheet("font-size: 14px; padding: 5px;"); self.result_label_2.setStyleSheet("font-size: 14px; padding: 5px;"); self.result_label_3.setStyleSheet("font-size: 14px; padding: 5px;"); self.result_layout.addRow(QLabel("선택지 1:"), self.result_label_1); self.result_layout.addRow(QLabel("선택지 2:"), self.result_label_2); self.result_layout.addRow(QLabel("선택지 3:"), self.result_label_3); vbox = QVBoxLayout(); vbox.addLayout(deck_select_layout); vbox.addWidget(self.run_button); vbox.addLayout(setup_layout); vbox.addLayout(self.result_layout); self.setLayout(vbox); self.setWindowTitle('스텔라 소라 트래커 (v4.8 - 최종 수정)'); self.setGeometry(300, 300, 400, 300); self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint);
        if self.deck_select_combo.count() > 0: self.on_deck_changed(self.deck_select_combo.currentText())
    def is_game_running(self):
        if not self.game_window_title: return False
        try: return len(gw.getWindowsWithTitle(self.game_window_title)) > 0
        except Exception: return False
    def run_full_setup(self):
        self.hide(); game_dialog = GameWindowSetupDialog(self); game_dialog.game_window_selected.connect(self.on_game_window_set);
        if game_dialog.exec() == QDialog.DialogCode.Accepted: print("1단계 완료. 2단계(좌표 설정) 시작 대기..."); QTimer.singleShot(2000, self.launch_coord_setup)
        else: print("1단계 취소됨."); self.show_error_message("설정이 완료되지 않았습니다. 메인 화면으로 돌아갑니다."); self.show(); self.load_config()
    def on_game_window_set(self, title): self.game_window_title = title
    def launch_coord_setup(self):
        print("launch_coord_setup 함수 실행 시작");
        if not self.is_game_running(): self.show_error_message(f"'{self.game_window_title}' 창이 닫혔습니다. 다시 설정해주세요."); self.show(); self.load_config(); return
        try:
            print("스크린샷 시도..."); screenshot = ImageGrab.grab()
            if screenshot: print(f"스크린샷 성공: {screenshot.size}"); print("SetupWindow 생성 시도..."); self.setup_window = SetupWindow(screenshot); self.setup_window.coordinates_saved.connect(self.on_setup_complete); self.setup_window.cancelled.connect(self.on_setup_cancelled)
            else: print("스크린샷 실패 (결과가 None)"); self.show_error_message("스크린샷 캡처에 실패했습니다 (결과 없음)."); self.show()
        except Exception as e: print(f"launch_coord_setup 오류: {e}"); self.show_error_message(f"스크린샷/설정 창 생성 오류: {e}\n권한 문제나 디스플레이 설정을 확인하세요."); self.show()
    def on_setup_complete(self, coordinates):
        self.coordinates = coordinates; config_data = {"game_window_title": self.game_window_title, "coordinates": self.coordinates}
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=2)
            self.load_config(); QMessageBox.information(self, "성공", "모든 설정이 'config.json' 파일에 저장되었습니다.")
        except Exception as e: self.show_error_message(f"config.json 저장 실패: {e}")
        self.show()
    def on_setup_cancelled(self):
        self.show_error_message("좌표 설정이 취소되었습니다. 설정을 다시 시작하세요."); self.load_config(); self.show()
    def on_deck_changed(self, deck_name):
        self.current_deck_potentials = self.user_decks.get(deck_name, {}).get("potentials", [])
    def preprocess_image(self, img):
        # (v4.7과 동일)
        gray_img = ImageOps.grayscale(img); threshold = 180; binary_img = gray_img.point(lambda p: 255 if p > threshold else 0); return binary_img

    # --- (★수정된 부분★) ---
    def run_ocr_check(self):
        if not self.is_game_running(): self.update_result_label(self.result_label_1, "GAME_NOT_RUNNING", ""); self.update_result_label(self.result_label_2, "GAME_NOT_RUNNING", ""); self.update_result_label(self.result_label_3, "GAME_NOT_RUNNING", ""); return
        try:
            img1_raw = ImageGrab.grab(bbox=self.coordinates['box1']); img2_raw = ImageGrab.grab(bbox=self.coordinates['box2']); img3_raw = ImageGrab.grab(bbox=self.coordinates['box3'])
            img1 = self.preprocess_image(img1_raw); img2 = self.preprocess_image(img2_raw); img3 = self.preprocess_image(img3_raw)
            tess_config = '--psm 6'
            
            # OCR 실행
            text1_raw = pytesseract.image_to_string(img1, lang='kor', config=tess_config).strip()
            text2_raw = pytesseract.image_to_string(img2, lang='kor', config=tess_config).strip()
            text3_raw = pytesseract.image_to_string(img3, lang='kor', config=tess_config).strip()
            
            # 한글+공백만 추출
            text1_kor = " ".join(re.findall(r'[가-힣]+', text1_raw))
            text2_kor = " ".join(re.findall(r'[가-힣]+', text2_raw))
            text3_kor = " ".join(re.findall(r'[가-힣]+', text3_raw))

        except Exception as e: self.show_error_message(f"OCR/스크린샷 오류: {e}\n좌표가 올바른지 확인하세요 (config.json)."); return
        
        # update_result_label 호출 시 원본과 한글 필터링 텍스트 전달
        self.update_result_label(self.result_label_1, text1_raw, text1_kor)
        self.update_result_label(self.result_label_2, text2_raw, text2_kor)
        self.update_result_label(self.result_label_3, text3_raw, text3_kor)
    # ------------------------

    def clean_text(self, text):
        # (v4.7과 동일) - 공백과 특수문자 제거
        if not isinstance(text, str): print(f"경고: clean_text 입력이 문자열 아님: {type(text)}"); return ""
        try: text = re.sub(r'[\n\t]+', ' ', text); text = re.sub(r'[\s\-.,:;\'\[\]•]+', '', text); return text
        except Exception as e: print(f"clean_text 오류 발생: {e} (입력: {text[:50]}...)"); return ""

    def extract_potential_name(self, deck_potential_raw):
        # (v4.7과 동일)
        if not isinstance(deck_potential_raw, str): print(f"경고: extract_potential_name 입력이 문자열 아님: {type(deck_potential_raw)}"); return ""
        try:
            last_bracket_index = deck_potential_raw.rfind(']');
            if last_bracket_index != -1: return deck_potential_raw[last_bracket_index + 1:].strip()
            else: return deck_potential_raw.strip()
        except Exception as e: print(f"extract_potential_name 오류 발생: {e} (입력: {deck_potential_raw[:50]}...)"); return ""

    # --- (★수정된 부분★) ---
    def update_result_label(self, label_widget, ocr_text_raw, ocr_text_kor):
        """GUI 레이블 업데이트 (한글 필터링된 텍스트로 비교)"""
        try:
            # 게임 실행 여부
            if ocr_text_raw == "GAME_NOT_RUNNING": label_widget.setText(f"게임({self.game_window_title[:20]}...) 없음"); label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: gray;"); return
            
            # 한글 필터링 결과가 비었는지 확인
            ocr_kor_cleaned = self.clean_text(ocr_text_kor) # 비교용 (공백 제거)

            # 한글 필터링 결과 자체가 없으면 (원본에 한글이 하나도 없었으면)
            if not ocr_kor_cleaned:
                display_text = "(인식 실패)" if not ocr_text_raw else ocr_text_raw
                label_widget.setText(display_text); label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: gray;"); return

            is_match = False
            if isinstance(self.current_deck_potentials, list):
                for deck_potential_raw in self.current_deck_potentials:
                    potential_name_only = self.extract_potential_name(deck_potential_raw)
                    if not isinstance(potential_name_only, str): continue
                    
                    deck_name_cleaned = self.clean_text(potential_name_only) # 비교용 (공백 제거)
                    if not isinstance(deck_name_cleaned, str): continue
                    
                    # (핵심) 정제된 '덱 이름'이, 정제된 '한글만 추출된 OCR 텍스트' 안에 포함되는지 확인
                    if deck_name_cleaned and ocr_kor_cleaned and deck_name_cleaned in ocr_kor_cleaned:
                        is_match = True
                        break
            else: print(f"경고: self.current_deck_potentials가 리스트가 아님: {type(self.current_deck_potentials)}")
            
            # 표시는 원본 OCR 결과로
            if is_match: label_widget.setText(f"★ {ocr_text_raw} ★"); label_widget.setStyleSheet("font-size: 16px; padding: 5px; color: green; font-weight: bold;")
            else: label_widget.setText(ocr_text_raw); label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: black;")
        except Exception as e: print(f"update_result_label 내부 오류: {e}"); label_widget.setText("(비교 오류)"); label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: red;")
    # ------------------------

    def show_error_message(self, message):
        print(f"오류: {message}"); QMessageBox.warning(self, "오류", message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TrackerApp()
    if not ex.load_config(): print("설정 파일 없음. 설정 마법사 시작..."); ex.hide(); QTimer.singleShot(100, ex.run_full_setup)
    else: print("설정 파일 로드 완료. 메인 창 표시."); ex.show()
    sys.exit(app.exec())
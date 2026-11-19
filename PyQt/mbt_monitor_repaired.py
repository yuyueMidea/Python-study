# -*- coding: utf-8 -*-
# =====================================================================
# mbt_monitor_repaired.py —— 由损坏文本整理还原（TV2.8 20250310）
# 还原说明见 repair_notes.md。标记含义：
#   【推断】/【重建】 根据残留片段或上下文推断，需对照原版确认
#   【原文损坏】/【无法确认】 原文内容丢失，此处仅保留骨架
# 注意：原“压成一行”的方法，其缩进嵌套为启发式还原，请重点回归测试。
# =====================================================================



import sys,os, re, binascii, csv, time, math, struct, copy, json, subprocess,platform
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
import pylightxl as xl
import pyqtgraph as pg
#调试方便临时注释
MIN_LEN=5
# 整数校验器 # 16位有符号数,正数范围[0x0000 到 0x7FFF(十进制 0 到 32767)];负数范围:[0x8000 到 0xFFFF（十进制 -32768 到 -1）]
# 设置从站地址的输入限制【1-255】
slaveAddrValidator = QRegExpValidator(QRegExp('^(25[0-5]|2[0-4][0-9]|[0-1]?[0-9]?[0-9])$'))
# 创建一个 QRegExp 对象，匹配 0 到 65535 的整数
int0_65535Validator = QRegExpValidator(QRegExp(r"^([0-9]|[1-9]\d|[1-9]\d{2}|[1-9]\d{3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$"))
# 定义正则表达式，匹配 -65535 到 65535 之间的整数
intValidator = QRegExpValidator(QRegExp(r'^-?(6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]?\d{0,4})$'))
intPositiveValidator = QIntValidator()
intPositiveValidator.setRange(0,1000000)
# 定义正则表达式，匹配 0 到 65535 的浮点数
doubleValidator = QRegExpValidator(QRegExp(r"^(6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|\d{1,4})(\.\d+)?$"))
# setNotation(notation)：设置浮点数的表示方式，可选的值包括 QDoubleValidator.StandardNotation（标准表示法）和 QDoubleValidator.ScientificNotation（科学计数法）。
hexValidator = QRegExpValidator(QRegExp("^[A-Fa-f0-9]{4}$"))
# 设置 正则表达式，显示输入0.0.0.0~255.255.255.255
ipValidator = QRegExpValidator(QRegExp('^((2[0-4]\d|25[0-5]|\d?\d|1\d{2})\.){3}(2[0-4]\d|25[0-5]|[01]?\d\d?)$'))
# 从封装的包里引入常用函数方法和通用类
from tools import (formatOption,getExecStrs,parse2bitSlice,replaceStrByIndexs, getreadcrc, getwritecrc, getwriteMulticrc, checkBufferSum, getSplitArr, calc_crc,calc_byte_crc, TimestampToRTC, RTCToTimestamp, getSliceChunkArr,str2float, split_bytes, getHigh4Low4, binary_search_nearest, decimal2hex, getCurrentStamp, set_all_buttons_noFocus, find_parent_layout, ComboCheckBox, EditableLabel, SwitchButton, ExtendedComboBox, CustomTextEdit, CustomToast, CustomDockWidget, QTextEditWithButtons, CustomToolBar)

import logging
if not os.path.exists('./exportlog'):
    os.makedirs('./exportlog')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[ logging.FileHandler("./exportlog/app.log"), logging.StreamHandler(sys.stdout) ])
logger = logging.getLogger(__name__)
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 添加错误日志记录
# 全局使用[cgitb]来捕获异常信息,界面不要突然退出！
tracelogDir = './tracelog'
if not os.path.exists(tracelogDir):
    os.makedirs(tracelogDir)
import cgitb
# cgitb.enable(
#     logdir=tracelogDir,
#     display=False,
#     context=5,
#     format='text',
# )
# 禁用下拉选自带的滚动事件防止误操作
class QComboBox(QComboBox):
    def wheelEvent(self, e):
        e.ignore()
        pass

class childFollowMoveDialog(QDialog):
    def __init__(self, parent=None):
        super(childFollowMoveDialog, self).__init__(parent)
        self.parentWin = parent
    def moveEvent(self,evt):
        # 移动弹框的时候，字弹框跟随一起移动位置
        if addressDialog.isVisible():
            addressDialog.setGeometry(self.geometry().left(), self.geometry().top()+120, 500, 300)
            addressDialog.raise_()
        if settingDialog.isVisible():
            calc_table_heihgt = 80+30*len(self.parentWin.selectedChannelMap)
            settingDialog.setGeometry(self.geometry().left(), self.geometry().top()+120, 600, calc_table_heihgt)
            settingDialog.raise_()
    def closeEvent(self,evt):
        # 关掉弹框的时候，也重开常规轮询的操作[]
        self.parentWin.plotGraphType = None
        self.parentWin.plotGraphFlag = False
        self.parentWin.writeLocalSettings()
        if self.parentWin.serialCom.isOpen():
            self.parentWin.send_time.start(100)
        if settingDialog.isVisible():
            settingDialog.close()
        if addressDialog.isVisible():
            addressDialog.close()

class MultiTabMonitor(QMainWindow):
    def __init__(self,parent=None):
        super(MultiTabMonitor, self).__init__(parent)
        logger.info("Main window initialized")
        # 设置窗口图标
        self.setWindowIcon( QIcon('./icons/monitor.png'))
        # 初始化所有的参数---初始化全局的一些变量、列表、对象集合
        self.initGlobalParams()
        self.loadConfigFile()
        # 读取多语言的json文件并初始化全局语言包
        self.reTranslateUI()
        #初始化状态条和菜单
        self.initStatusBar()
        self.initMenuList()
        self.loadParameter()
        #开始加载常规轮询的配置文件生成节点
        self.loadChannelList()
        #加载选择通道的列表
        self.initTabNodeList()
        #默认打开密码输入的弹框，权限管理 # 渲染未完成，延迟0.5秒钟再切换到弹框
        # self.execDelayTimer.singleShot(500,lambda: passwordDialog.show())
        #
    def initMenuList(self):
        self.dev_version = 'TV2.8(20250310)'
        self.setWindowTitle('{}_{}'.format(self.langData.get('monitor_name'), self.dev_version))
        self.menuList = self.menuBar()
        # 禁用右键菜单中的勾选框
        self.menuList.setContextMenuPolicy(Qt.PreventContextMenu)
        self.settingMenu = self.menuList.addMenu(self.langData.get('setting_menu'))
        self.toolMenu = self.menuList.addMenu(self.langData.get('tool_menu'))
        self.guiMenu = self.menuList.addMenu(self.langData.get('gui_menu'))
        self.helpMenu = self.menuList.addMenu(self.langData.get('help_menu'))
        # 工具部分的菜单
        self.openBufferAction = QAction(QIcon('./icons/connect_device.png'), self.langData.get('buffer_info'), triggered=self.open_bufferDialog)
        self.otaAction = QAction(QIcon('./icons/fileUpdate.png'), self.langData.get('ota_update'), triggered=self.open_otaDialog)
        self.faultLogAction = QAction(QIcon('./icons/transfer2.png'),self.langData.get('file_upload'), triggered=self.open_faultLogDialog)
        self.opendataRWAction = QAction(QIcon('./icons/setting2.png'), self.langData.get('data_read_write'), triggered=self.open_dataRWDialog)
        self.plotTabAction = QAction(QIcon('./icons/datawave.png'), self.langData.get('plot_tab_name'), triggered=self.toggle_plotSoftDataDialog)
        self.registerCfgAction = QAction(QIcon('./icons/import3.png'), self.langData.get('register_cfg'), triggered=self.open_ioDialog)
        self.toolMenu.addAction(self.openBufferAction)
        self.toolMenu.addSeparator()
        self.toolMenu.addAction(self.otaAction)
        self.toolMenu.addSeparator()
        self.toolMenu.addAction(self.faultLogAction)
        self.toolMenu.addSeparator()
        self.toolMenu.addAction(self.opendataRWAction)
        self.toolMenu.addSeparator()
        self.toolMenu.addAction(self.plotTabAction)
        #调试方便临时注释
        self.toolMenu.addSeparator()
        self.toolMenu.addAction(self.registerCfgAction)
        self.toolMenu.addAction(self.plotDialogAction)
        # 设置部分的菜单[passwordset]
        self.pwdSetAction = QAction(QIcon('./icons/passwordset.png'), self.langData.get('password_management'), triggered=lambda: passwordDialog.show())
        self.comSetAction = QAction(QIcon('./icons/setting3.png'), self.langData.get('communncation_set'), triggered=lambda: comSetDialog.show())
        self.pinTopAction = QAction(QIcon('./icons/pintop.png'), self.langData.get('pin_top'))
        self.pinTopAction.setCheckable(True)
        self.pinTopAction.triggered[bool].connect(self.setWindowStayTop)
        self.setDockAction = QAction(self.langData.get('msg_console'))
        self.setDockAction.setCheckable(True)
        self.setDockAction.triggered[bool].connect(self.toggle_dock_widget)
        self.settingMenu.addAction(self.pwdSetAction)
        self.settingMenu.addSeparator()
        self.settingMenu.addAction(self.comSetAction)
        self.settingMenu.addSeparator()
        self.settingMenu.addAction(self.pinTopAction)
        self.settingMenu.addSeparator()
        self.settingMenu.addAction(self.setDockAction)
        self.fontAction = QAction(QIcon('./icons/fontsize.png'), self.langData.get('font_change'), triggered=self.onFontChange)
        self.styleAction = QAction(QIcon('./icons/expand.png'), self.langData.get('window_style'))
        self.guiMenu.addAction(self.fontAction)
        self.guiMenu.addSeparator()
        # 创建windowStyles二级菜单
        self.styleAction = QMenu(self.langData.get('window_style'))
        self.guiMenu.addMenu(self.styleAction)
        winStyleGroup = QActionGroup(self)
        styleKeys = QStyleFactory.keys()
        for styleItem in styleKeys:
            styleAct = QAction(styleItem)
            styleAct.setCheckable(True)
            if self.winType == styleItem:
                styleAct.setChecked(True)
                app.setStyle(QStyleFactory.create(styleItem))
            styleAct.triggered.connect(self.onAppStyleChange)
            winStyleGroup.addAction(styleAct)
            self.styleAction.addAction(styleAct)

        # 创建languages二级菜单[QIcon('./icons/language.png')]
        self.guiMenu.addSeparator()
        self.menusAction = QMenu(self.langData.get('lang_menu'))
        self.guiMenu.addMenu(self.menusAction)
        menusActionGroup = QActionGroup(self)
        # 添加多语言选项【根据配置文件动态创建】
        self.langActionList = []
        for langTxt in self.languageMap.keys():
            currentLang = self.languageMap.get(langTxt).get('language')
            toggleLangAction = QAction(currentLang)
            toggleLangAction.setCheckable(True)
            toggleLangAction.setProperty('name', langTxt)
            if self.langType == langTxt:
                toggleLangAction.setChecked(True)
            toggleLangAction.triggered[bool].connect(self.toggleLangTrigger)
            menusActionGroup.addAction(toggleLangAction)
            self.menusAction.addAction(toggleLangAction)
            self.langActionList.append(toggleLangAction)
        # last_section[userHelp]
        self.helpAction = QAction(QIcon('./icons/help.png'), self.langData.get('user_help'), triggered=self.onHelpAbout)
        self.helpMenu.addAction(self.helpAction)
        # 工具栏菜单部分
        fileMenu = self.addToolBar('File1')
        fileMenu = CustomToolBar('toolbar1')
        self.addToolBar(fileMenu)
        fileMenu.setMovable(False)
        # 禁止工具栏移动
        fileMenu.setStyleSheet("QToolBar{ background: #ccc;}")
        self.serialPortList = QComboBox()
        self.initSerialPortList()
        self.baudRateList = QComboBox()
        self.baudRateList.addItems(["9600", "14400", "19200", "38400", "56000", "57600", "115200", "256000", "460800", "512000"])
        self.baudRateList.setEditable(True)
        self.baudRateList.setCurrentText(str(self.configSettingMap.get('comBaud', '38400')))
        self.portAction = QAction(QIcon('./icons/refresh.png'), self.langData.get('serial_port'), triggered=self.refreshPort)
        fileMenu.addAction(self.portAction)
        fileMenu.addWidget(self.serialPortList)
        self.serialPortList.setCurrentText(str(self.configSettingMap.get('comName')))
        fileMenu.addSeparator()
        self.baudLabel = QLabel(self.langData.get('baud_rate'))
        self.baudLabel.setFixedWidth(60)
        self.baudLabel.setAlignment(Qt.AlignHCenter|Qt.AlignVCenter)
        fileMenu.addWidget(self.baudLabel)
        fileMenu.addWidget(self.baudRateList)
        fileMenu.addSeparator()
        self.key_text_toggle = QPushButton(self.langData.get('open_port'), clicked=self.Com_Toggle_Button_clicked)
        fileMenu.addWidget(self.key_text_toggle)
        self.open_dir_btn = QPushButton(self.langData.get('open_log_dir'), clicked=self.openExportLogDir)
        fileMenu.addWidget(self.open_dir_btn)
        # 创建一个水平间距项20*10
        spacerItem = QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum)
        fileMenu.addItem(spacerItem)
        # 设置组件之间的间距
        fileMenu.layout().setSpacing(10)
        self.listenerChk = QCheckBox(self.langData.get('listener_mode'))
        self.listenerChk.toggled.connect(self.listenerToggled)
        self.listenerChk.setStyleSheet('margin:0 20px;')
        fileMenu.addWidget(self.listenerChk)
        self.saveLoopDataChk = QCheckBox(self.langData.get('auto_save_data'))
        self.saveLoopDataChk.setChecked(True)
        self.saveLoopDataChk.setStyleSheet('margin:0 20px;')
        fileMenu.addWidget(self.saveLoopDataChk)
        fileMenu.addStretch(1)
        self.levelLabel = QLabel(self.langData.get('pwd_level'))
        self.passwordLabel = QLabel('3')
        fileMenu.addWidget(self.levelLabel)
        fileMenu.addWidget(self.passwordLabel)
        # QShortcut控件方式--# 通过QShortcut控件设置快捷方式，触发槽函数
        sc1 = QShortcut(QKeySequence('Ctrl+Alt+R'),self, activated=self.reStartApp_bySC)
        sc2 = QShortcut(QKeySequence('Ctrl+F12'),self, activated=self.toggle_dock_widget_bySC)
        # 图标旁边显示文本
        fileMenu.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        fileMenu.setIconSize(QSize(16,16))
        #打开当前目录
    def openExportLogDir(self):
        os.startfile( os.getcwd() )
    def resetListener(self):
        self.listenerState='readReg'
        self.historyData = b''
        self.readRegAddr = ''
        self.readRegCount = 0
        self.readRegBufferCount = 8

    def listenerToggled(self, state):
        if self.listenerChk.isChecked():
            self.resetListener()
            self.send_time.stop()
            self.readRegTitle = list(self.editableListMap.keys())[0] #默认第一个tab名
            self.setGlobalBoxDisabled(True)
            if not self.disconnectedTimer.isActive():
                self.disconnectedTimer.start(1000)
        else:
            if self.disconnectedTimer.isActive():
                self.disconnectedTimer.stop()
            self.setInitGroupAddrList()
            self.setGlobalBoxDisabled(False)
            if self.serialCom.isOpen():
                self.loopOneRead()

    def pwdConfirmSet(self):
        pwdInput = passwordNode.text().strip()
        if pwdInput=='57632':
            pwdLevel.setText('{} 3'.format(self.langData.get('pwd_level')))
            self.passwordLabel.setText('3')
            self.setGlobalBoxDisabled(False)
        elif pwdInput=='25768':
            pwdLevel.setText('{} 2'.format(self.langData.get('pwd_level')))
            self.passwordLabel.setText('2')
            self.setGlobalBoxDisabled(False)
        elif pwdInput=='12345':
            pwdLevel.setText('{} 1'.format(self.langData.get('pwd_level')))
            self.passwordLabel.setText('1')
            self.setGlobalBoxDisabled(False)
        else:
            pwdLevel.setText('{} 0'.format(self.langData.get('pwd_level')))
            self.passwordLabel.setText('0')
            self.setGlobalBoxDisabled(True)
        passwordDialog.close()

    def setGlobalBoxDisabled(self, enableFlag):
        for ke, tabItem in self.globlaBoxNodeMap.items():
            for box in tabItem:
                box.setDisabled(enableFlag)

    def confirmComSet(self):
        comName = self.serialPortList.currentText()
        comBaud = int(self.baudRateList.currentText())
        # 设置串口名称
        self.serialCom.setPortName(comName)
        # 设置波特率
        self.serialCom.setBaudRate(comBaud)
        # 设置数据位
        self.serialCom.setDataBits(int(comDatabitsList.currentText()))
        # 设置校验位
        self.serialCom.setParity(comParityList.currentIndex())
        # # 设置停止位
        stopbits = 3 if comStopbitsList.currentText()=="1.5" else int(comStopbitsList.currentText())
        self.serialCom.setStopBits(stopbits)
        # 设置流控制
        self.serialCom.setFlowControl(comFlowconList.currentIndex())
        self.dock_content.append('======name:{},bauarate:{}, databit:{}, parity:{}, stopbit:{}, flowc:{}=========:'.format(comName, comBaud ,int(comDatabitsList.currentText()), comParityList.currentIndex(), stopbits, comFlowconList.currentIndex()) )
        # # set_time_params
        self.updateStampWaitTime = int(paramSetdelayTime.text())
        self.loopWaitTime = int(paramSetReadTime.text())
        self.writeWaitTime = int(paramSetWriteTime.text())
        self.maxfileSize = int(paramSetFileSize.text())
        self.autoSaveInterval = int(paramSetSaveInterval.text())
        self.sleepTime = float(int(paramSetSleepInterval.text())/1000)
        self.dock_content.append('===> updateStampWaitTime_:{}, loopWaitTime_:{}, writeWaitTime_:{}, maxfileSize_:{}, autoSaveInterval_:{}, sleepTime_:{}'.format(self.updateStampWaitTime, self.loopWaitTime, self.writeWaitTime, self.maxfileSize, self.autoSaveInterval, self.sleepTime ))
        comSetDialog.close()

    def toggleLangTrigger(self):
        langItem = self.sender().property('name')
        for actNode in self.langActionList:
            if actNode.property('name') == langItem:
                self.langType = langItem
                actNode.setChecked(True)
            else:
                actNode.setChecked(False)
        self.langData = self.languageMap.get(self.langType)
        self.configSettingMap['langType'] = self.langType
        if self.langType != self.latestLangType:
            self.latestLangType = self.langType
        self.toolMenu.setTitle(self.langData.get('tool_menu'))
        self.settingMenu.setTitle(self.langData.get('setting_menu'))
        self.guiMenu.setTitle(self.langData.get('gui_menu'))
        self.helpMenu.setTitle(self.langData.get('help_menu'))
        self.registerCfgAction.setText(self.langData.get('register_cfg'))
        self.comSetAction.setText(self.langData.get('communncation_set'))
        self.plotTabAction.setText(self.langData.get('plot_tab_name'))
        self.faultLogAction.setText(self.langData.get('file_upload'))
        self.pwdSetAction.setText(self.langData.get('password_management'))
        passwordDialog.setWindowTitle(self.langData.get('password_management'))
        comSetDialog.setWindowTitle(self.langData.get('communncation_set'))
        self.pinTopAction.setText(self.langData.get('pin_top'))
        self.setDockAction.setText(self.langData.get('msg_console'))
        self.fontAction.setText(self.langData.get('font_change'))
        self.styleAction.setTitle(self.langData.get('window_style'))
        self.menusAction.setTitle(self.langData.get('lang_menu'))
        self.helpAction.setText(self.langData.get('user_help'))
        # 文件上传弹框的对应多语言
        faultLogDialog.setWindowTitle(self.langData.get('file_upload'))
        logTableList.setHorizontalHeaderLabels([self.langData.get('file_name'), self.langData.get('file_record'), self.langData.get('file_record_len'), self.langData.get('file_starttime'), self.langData.get('file_endtime'), self.langData.get('file_operation_col')])
        # 表格第五列的按钮文本同时也要设置多语言
        for rowID in range(logTableList.rowCount()):
            btnwidget = logTableList.cellWidget(rowID, 5)
            if btnwidget:
                btnwidget.setText(self.langData.get('file_read_btn1'))
        unitPackageLenLabel.setText(self.langData.get('unit_packageLen'))
        logSlaveAddrLabel.setText(self.langData.get('station_address'))
        recordCountLabel.setText('{}: {}'.format(self.langData.get('record_count'), len(self.logdataMapList)))
        filterSearchBtn1.setText(self.langData.get('file_refresh'))
        fileDetailBox1.setTitle(self.langData.get('file_detail'))
        logDetailFileLabel.setText(self.langData.get('file_name'))
        filterdownloadBtn.setText(self.langData.get('file_read'))
        filterStopBtn.setText(self.langData.get('file_read_stop'))
        filterTime1Label.setText(self.langData.get('file_starttime'))
        filterTime2Label.setText(self.langData.get('file_endtime'))
        fileProgressLabel.setText(self.langData.get('file_progress'))
        fileOperation1.setTitle(self.langData.get('file_operation'))
        filePath1Label.setText(self.langData.get('log_file_path'))
        filePath2Label.setText(self.langData.get('parser_file_path'))
        filePath3Label.setText(self.langData.get('output_file_path'))
        filePathBtn1.setText(self.langData.get('import_logfile'))
        filePathBtn2.setText(self.langData.get('import_parser'))
        filePathBtn3.setText(self.langData.get('file_transform'))
        filePathBtn4.setText(self.langData.get('open_csvfile'))
        clearLogBtn.setText(self.langData.get('file_log_clear'))
        openFile_dir_btn.setText(self.langData.get('open_directory'))
        # 加载界面上工具栏节点的对应多语言
        self.listenerChk.setText(self.langData.get('listener_mode'))
        self.saveLoopDataChk.setText(self.langData.get('auto_save_data'))
        self.open_dir_btn.setText(self.langData.get('open_log_dir'))
        self.baudLabel.setText(self.langData.get('baud_rate'))
        self.portAction.setText(self.langData.get('serial_port'))
        self.otaAction.setText(self.langData.get('ota_update'))
        self.openBufferAction.setText(self.langData.get('buffer_info'))
        self.opendataRWAction.setText(self.langData.get('data_read_write'))
        if self.serialCom.isOpen():
            self.key_text_toggle.setText(self.langData.get('close_port'))
        else:
            self.key_text_toggle.setText(self.langData.get('open_port'))
        # 通用部分的多语言配置
        mcuGbox1.setTitle(self.langData.get('mcu_addr_setting'))
        mcuLabel1.setText(self.langData.get('register_name'))
        mcuLabel2.setText(self.langData.get('register_addr'))
        mcuBtn1.setText(self.langData.get('read_btn'))
        mcuBtn2.setText(self.langData.get('write_btn'))
        mcuGbox2.setTitle(self.langData.get('mcu_addr_value'))
        mcuLabel2_1.setText(self.langData.get('register_name'))
        mcuLabel3.setText(self.langData.get('register_value'))
        mcuLabel4.setText(self.langData.get('data_type'))
        mcuBtn3.setText(self.langData.get('read_btn'))
        mcuBtn4.setText(self.langData.get('write_btn'))
        # 设置标题头相关的多语言
        pwdLevel.setText(self.langData.get('pwd_level'))
        self.levelLabel.setText(self.langData.get('pwd_level'))
        self.setWindowTitle('{}_{}'.format(self.langData.get('monitor_name'), self.dev_version))
        addressDialog.setWindowTitle(self.langData.get('channel_address_dialog'))
        settingDialog.setWindowTitle(self.langData.get('set_channel'))
        plotMonitorDialog.setWindowTitle(self.langData.get('plot_realTime_data'))
        plotWidDialog.setWindowTitle(self.langData.get('plot_tab_name'))
        slaveAddrLabel.setText(self.langData.get('station_address'))
        self.readBtnNode.setText(self.langData.get('read_btn'))
        self.writeBtnNode.setText(self.langData.get('write_btn'))
        self.stationLabel.setText(self.langData.get('station_address'))
        self.addrLabel.setText(self.langData.get('register_address'))
        self.countLabel.setText(self.langData.get('register_count'))
        self.read_write_box.setTitle(self.langData.get('read_write_tips'))
        self.openSelectBtn.setText(self.langData.get('select_channel'))
        self.settingBtn.setText(self.langData.get('set_channel'))
        self.screenWLabel.setText(self.langData.get('screen_width'))
        self.saveDataNode.setText(self.langData.get('save_data_btn'))
        self.openDataNode.setText(self.langData.get('open_history_data'))
        self.saveDataNode2.setText(self.langData.get('save_data_btn'))
        self.openDataNode2.setText(self.langData.get('open_history_data'))
        clear_graph_outputNode2.setText(self.langData.get('clear_display'))
        self.clearDataNode.setText(self.langData.get('clear_cache_data'))
        self.resetNode.setText(self.langData.get('refresh_plot'))
        self.toggleCursorBtn.setText(self.langData.get('plot_tip'))
        self.resetNode2.setText(self.langData.get('refresh_plot'))
        self.toggleCursorBtn2.setText(self.langData.get('plot_tip'))
        self.chk_cursor.setText(self.langData.get('vernier_caliper'))
        self.startButtonNode.setText(self.langData.get('start_monitoring'))
        self.stopButtonNode.setText(self.langData.get('stop_monitoring'))
        line2Label1.setText(self.langData.get('mode_setting'))
        line2Label2.setText(self.langData.get('data_source'))
        self.setAddressBtn.setText(self.langData.get('set_address'))
        self.triggerlabel.setText(self.langData.get('trigger_mode'))
        self.triggerManualBtn.setText(self.langData.get('manual_trigger'))
        self.triggerlabel2.setText(self.langData.get('trigger_channel'))
        self.triggerlabel3.setText(self.langData.get('trigger_value'))
        refreshLabel.setText(self.langData.get('sample_circle'))
        sampleLabel.setText(self.langData.get('sample_count_time'))
        cacheLenLabel.setText(self.langData.get('cache_length'))
        clear_graph_outputNode.setText(self.langData.get('clear_display'))
        saveImg_Button_Node.setText(self.langData.get('save_as_image'))
        chk_gridmode.setText(self.langData.get('set_grid_line'))
        chk_mousemode.setText(self.langData.get('set_mouse_mode'))
        chk_mouseXEnable.setText(self.langData.get('set_mouseX_enable'))
        chk_mouseYEnable.setText(self.langData.get('set_mouseY_enable'))
        chk2_mouseXEnable.setText(self.langData.get('set_mouseX_enable'))
        chk2_mouseYEnable.setText(self.langData.get('set_mouseY_enable'))
        # 选择通道的弹框区域相关的对应的多语言
        channelDialog.setWindowTitle(self.langData.get('select_channel'))
        hbox_wrapper.setTitle(self.langData.get('setting'))
        filterSearchLabel.setText(self.langData.get('filter_search_select'))
        confirmBtnNode.setText(self.langData.get('confirm_btn'))
        resetBtnNode.setText(self.langData.get('reset_btn'))
        # 导入导出弹框区域相关的对应的多语言
        ioDialog.setWindowTitle(self.langData.get('register_cfg'))
        importCsvbtn.setText(self.langData.get('open_csv'))
        importPwfbtn.setText(self.langData.get('open_pwf'))
        stationAddrNode.setText(self.langData.get('station_address'))
        readRawValBtn.setText(self.langData.get('read_raw_value'))
        writeListBtn.setText(self.langData.get('write_btn'))
        multiWriteListBtn.setText(self.langData.get('write_batch'))
        savecsvBtn.setText(self.langData.get('saveAs_csv'))
        savepwfBtn.setText(self.langData.get('saveAs_pwf'))
        ioTableList.setHorizontalHeaderLabels([self.langData.get('write_address'), self.langData.get('write_value'), self.langData.get('raw_value'), self.langData.get('write_state')])
        channelTableList.setHorizontalHeaderLabels([self.langData.get('data_address'), self.langData.get('data_name'), self.langData.get('channel_color'), self.langData.get('channel_y_scale'), self.langData.get('channel_y_offset'), 'XA-XB','YA','YB','YA-YB'])
        addrTableList.setHorizontalHeaderLabels(['ID', self.langData.get('data_name'), self.langData.get('data_address'), self.langData.get('data_offset'), self.langData.get('data_type'), self.langData.get('data_precision'), self.langData.get('data_operate')])
        setChannelResetbtn.setText(self.langData.get('reset_btn'))
        settingConfirmBtn.setText(self.langData.get('set_address_confirmBtn'))
        addOneBtnNode.setText(self.langData.get('set_address_addBtn'))
        # 报文展示弹框区域相关的对应的多语言
        bufferDialog.setWindowTitle(self.langData.get('buffer_dialog'))
        dataRWDialog.setWindowTitle(self.langData.get('data_read_write'))
        sendLabel.setText(self.langData.get('send_count')+':')
        receiveLabel.setText(self.langData.get('receive_count')+':')
        self.toggle_text.setText(self.langData.get('update_buffer'))
        saveTxtBtn.setText(self.langData.get('save_buffer'))
        clearBtn.setText(self.langData.get('clear_buffer'))
        self.searchTextBox.setText(self.langData.get('input_search_buffer'))
        searchTextBtn.setText(self.langData.get('search_buffer'))
        appendSendBtn.setText(self.langData.get('send_btn'))
        self.intervalCheckbox.setText(self.langData.get('send_interval'))
        # ota弹框区域相关的对应的多语言
        otaDialog.setWindowTitle(self.langData.get('ota_update_dialog'))
        self.ota_setting_box.setTitle(self.langData.get('ota_setting'))
        otaSlaveAddrLabel.setText(self.langData.get('station_address'))
        otaUpdateDev.setText(self.langData.get('update_dev'))
        otaFileSizelabel.setText(self.langData.get('file_size'))
        otaFilecrcLabel.setText(self.langData.get('file_crc'))
        otaFileByteLen.setText(self.langData.get('byte_len'))
        otaFileBin.setText(self.langData.get('ota_file'))
        self.readTriggerBtn.setText(self.langData.get('read_file'))
        self.ota_state_box.setTitle(self.langData.get('ota_state'))
        otaSNlabel.setText(self.langData.get('ota_sn'))
        otaVersionlabel.setText(self.langData.get('ota_version'))
        self.readDevBtn.setText(self.langData.get('read_info'))
        self.ota_operation_box.setTitle(self.langData.get('update_operation'))
        updateStatelabel.setText(self.langData.get('update_state'))
        self.updateTiptext.setText(self.langData.get('update_state'))
        updateProgresslabel.setText(self.langData.get('update_progress'))
        self.updateTriggerBtn.setText(self.langData.get('update_start'))
        for tab_name in self.langNodeMap:
            self.langNodeMap[tab_name][0].setText(self.langData.get('station_address'))
            self.langNodeMap[tab_name][1].setText(self.langData.get('common_loop'))
            self.langNodeMap[tab_name][2].setText(self.langData.get('send_count')+': 0')
            self.langNodeMap[tab_name][3].setText(self.langData.get('receive_count')+': 0')
            self.langNodeMap[tab_name][4].setText(self.langData.get('clear_btn'))
            self.langNodeMap[tab_name][5].setText(self.langData.get('plot_realTime_data'))
            self.langNodeMap[tab_name][6].setTitle(self.langData.get('setting'))

    def reTranslateUI(self):
        filepath = "./config/language.json"
        if not os.path.exists(filepath):
            return QMessageBox.critical(self, 'critical_err','--- missing file: {}, please check! ---'.format(filepath) )
        try:
            with open(filepath, 'r',encoding='utf8') as f:
                self.languageMap = json.load(fp=f)
                self.langData = self.languageMap.get(self.langType)
        except Exception as e:
            logger.error('--- open_language_json_file_ERR: {}! ---'.format(e))
            CustomToast('--- open_language_json_file_ERR: {}! ---'.format(e), timeout=4000)

    def setWindowStayTop(self, state):
        m_flags = self.windowFlags() # 没有这行代码会使窗口的标题栏消失
        if state:
            self.windowHandle().setFlags(m_flags | Qt.WindowType.WindowStaysOnTopHint)
            self.sender().setIcon(QIcon(''))
        else:
            self.windowHandle().setFlags(m_flags | Qt.WindowType.Widget)
            self.sender().setIcon(QIcon('./icons/pintop.png'))

    def toggle_dock_widget(self, state):
        if state:
            # 创建 QDockWidget
            self.dock_widget = CustomDockWidget(self.langData.get('msg_console'), self)
            self.dock_widget.setAllowedAreas(Qt.BottomDockWidgetArea)
            self.dock_widget.setWidget(self.dock_content)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_widget)
            # 将 QDockWidget 停靠在底部区域,最高度400# 设置初始高度60
            self.dock_widget.setMaximumHeight(400)
            self.resizeDocks([self.dock_widget], [60], Qt.Vertical)
            self.dock_widget.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        else:
            if self.dock_widget:
                self.dock_widget.close()

    def toggle_dock_widget_bySC(self):
        if self.dock_widget:
            return self.toggle_dock_widget(True)
        self.setDockAction.setChecked(True)

    def onFontChange(self):
        cfont, ok = QFontDialog.getFont()
        if ok:
            self.dock_content.append(f'======font_: {cfont}, fsize_: {cfont.pointSize() }, ffamily_: {cfont.family()}, fstyle_: {cfont.styleName()},==========')
            app.setFont(cfont)
            self.tw.tabBar().setFont(cfont)
            # 针对tab页下面的label标签设置一下字体
            channelDialog.setStyleSheet(f"font-family:{cfont.family()}; font-size:{cfont.pointSize()}; font-style:{cfont.styleName()}")
            for chkItem in self.tw.findChildren(QCheckBox):
                chkItem.setFont(cfont)
            groupList = self.tw.findChildren(QGroupBox)
            for tabgroup in groupList:
                tabgroup.setFont(cfont)
            inputList = self.tw.findChildren(QLineEdit)
            for inputItem in inputList:
                inputItem.setFont(cfont)
            comboList = self.tw.findChildren(QComboBox)
            for cItem in comboList:
                cItem.setFont(cfont)
            labelList = self.tw.findChildren(QLabel)
            for item in labelList:
                item.setStyleSheet(f"font-family:{cfont.family()}; font-size:{cfont.pointSize()}; font-style:{cfont.styleName()}")
            self.configSettingMap['fontFamily'] = cfont.family()
            self.configSettingMap['fontSize'] = cfont.pointSize()

    def onAppStyleChange(self):
        styleText = self.sender().text()
        self.winType = styleText
        self.configSettingMap['winType'] = styleText
        # app.setStyle(QStyleFactory.create(styleText))
        styleKeys = QStyleFactory.keys()
        styleItem, ok = QInputDialog.getItem(self, '选择项', '请选择界面风格:', styleKeys, 0, False)
        if ok:
            app.setStyle(QStyleFactory.create(styleItem))

    def initStatusBar(self):
        self.statusBar = QStatusBar(self)
        self.globalStatus = QLabel(self.langData.get('not_connect'))
        self.globalStatus.setAlignment(Qt.AlignRight)
        self.globalStatus.setStyleSheet('padding-right:3px;')
        self.progressbar02 = QProgressBar(self, minimum=0, maximum=2,textVisible=False, objectName="progressbar02")
        self.progressbar02.setStyleSheet('min-height: 16px;max-height: 16px;min-width: 50px;max-width: 50px;')
        self.globalStatusHbox = QHBoxLayout()
        self.globalStatusHbox.addWidget(self.globalStatus)
        self.globalStatusHbox.addWidget(self.progressbar02)
        self.globalStatusHbox.setSpacing(0)
        self.globalStatusHbox.setContentsMargins(0,0,0,0)
        self.globalStatusWid = QWidget()
        self.globalStatusWid.setLayout(self.globalStatusHbox)
        self.statusBar.addPermanentWidget(self.globalStatusWid)
        #添加一个显示永久信息的标签控件
        self.globalStatus = QLabel(self.langData.get('not_connect'))
        self.globalStatus.setAlignment(Qt.AlignRight)
        self.statusBar.addPermanentWidget(self.globalStatus)
        self.setStatusBar(self.statusBar)

    def setStatusBarColor(self, color='black', timeout=3000):
        self.statusBar.setStyleSheet(f"color: {color};")
        QTimer.singleShot(timeout, lambda: self.statusBar.setStyleSheet(''))

    def reStartApp_bySC(self):
        cmd = 'mbt_monitor.exe'
        if not os.path.exists(cmd):
            return CustomToast('--- missing cmd_exe: {}, please check! ---'.format(cmd), color='red', timeout=5000 )
        # 重启之前先保存数据，避免遗漏
        self.saveLoopDataFile()
        self.saveBufferListItem()
        QCoreApplication.quit()
        process1 = QProcess()
        process1.startDetached(cmd)

    # 加载参数配置文件
    def loadParameter(self):
        # 找到当前文件夹目录下面的配置文件,并开始读取
        if not os.path.exists('./config/parameter.xlsx'):
            return QMessageBox.critical(self, self.langData.get('critical_msg'), '缺少配置文件[parameter.xlsx],请检查!')
        try:
            with open('./config/parameter.xlsx', 'rb') as f:
                self.fData = xl.readxl(f)
                self.tabTitleList = []
                self.tabAutoLoopList = []
                self.maxResponseIdx = 0
                self.globalReadTimes=1
                for ws_name in self.fData.ws_names:
                    contentArr = [] #存储每个tab页的点位信息
                    contentRawArr = [] #每个tab的【所有】点位列表
                    contentReadArr = [] #每个tab的【常规轮询的】点位信息列表
                    autoLoopFlag = False #每个tab页是否默认轮询
                    self.tabTitleList.append(ws_name)
                    self.showtypeListMap[ws_name] = []
                    cell_A1 = str(self.fData.ws(ws=ws_name).index(row=1, col=1))
                    cell_A2 = str(self.fData.ws(ws=ws_name).index(row=1, col=2))
                    if cell_A2=='autoLoop': autoLoopFlag = True
                    if not cell_A1.startswith('connectId:'):
                        self.stationAddress = 1 #从机地址的缺省值默认为1
                        self.showMessage('{}, missing_connectID!'.format(ws_name))
                    else:
                        self.stationAddress = int(cell_A1.split(':')[1])
                    # 开始遍历每行数据，并统一格式处理
                    for (line,regItem) in enumerate(self.fData.ws(ws=ws_name).rows):
                        if line<2: continue
                        regItem = [str(i) for i in regItem]
                        # 长度不足的补空,防止报错
                        regItemLen = len(regItem)
                        if regItemLen < 10: regItem.extend(['']*(10 - regItemLen))
                        if '&' in regItem[0]: regItem[0]=regItem[0].replace('amp;','')
                        if regItem[0]!='' and regItem[1]=='':
                            contentArr.append({'name': regItem[0]})
                            continue
                        cellAddr = int(regItem[1])
                        if regItem[2]=='WO':
                            self.writeOnlyList.append(regItem)
                        else:
                            contentRawArr.append(cellAddr)
                        if regItem[9].startswith('READTIMES'):
                            self.readOnceArr.append(cellAddr)
                            self.readOnceArrCopy.append(cellAddr)
                            repeatReadTimes = int(getExecStrs(regItem[9]))
                            self.readTimesMap[cellAddr] = repeatReadTimes
                            self.readTimesMapCopy[cellAddr] = repeatReadTimes
                            self.globalReadTimes = self.globalReadTimes if self.globalReadTimes>repeatReadTimes else repeatReadTimes
                        else:
                            contentReadArr.append(cellAddr)
                            self.regAddrList.append(cellAddr)
                        # self.regNameList.append(regItem[0])
                        self.nameAddressMap[regItem[0]] = cellAddr
                        #更新点位数据的信息：名称地址单位等等，
                        currentMap = {
                            'name': regItem[0],
                            'addr': regItem[1],
                            'attr': 'RW' if regItem[2]=='' else regItem[2],
                            'unit': regItem[3],
                            'precision': 0 if regItem[4]=='' else int(regItem[4]),
                            'showType': 'UNSIGNED' if regItem[5]=='' else regItem[5],
                            'options': formatOption(regItem[6]) if regItem[6] else [],
                            'dataSource': regItem[7],
                            'bitslice': '' if regItem[7]=='' else getExecStrs(regItem[7]),
                            'item485Id': self.stationAddress,
                            'highLightOptions': formatOption(regItem[8]) if regItem[8] !='' else [],
                            'readTimes': '' if regItem[9]=='' else getExecStrs(regItem[9]),
                            'tabTitle': ws_name
                        }
                        # 针对多个连续读点的属性添加多的点位
                        if currentMap['dataSource']=='Reg32':
                            contentRawArr.append(cellAddr+1)
                            contentReadArr.append(cellAddr+1)
                            self.regAddrList.append(cellAddr+1)
                        if currentMap['dataSource'].startswith('RegArr'):
                            addrCount = int(currentMap['dataSource'].replace('RegArr',''))
                            for nx in range(1, addrCount):
                                contentRawArr.append(cellAddr+nx)
                                contentReadArr.append(cellAddr+nx)
                                self.regAddrList.append(cellAddr+nx)
                        if regItem[5]!='RESERVED':
                            contentArr.append(currentMap)
                            self.regItemMapArr.append(currentMap)
                        if currentMap.get('showType')=='SIGNED':
                            self.signedAddrList.append(int(currentMap.get('addr')))
                            self.showtypeListMap[ws_name].append(int(currentMap.get('addr')))
                    # 归并一下每个tab页的读点信息【按照固定长度来排序分块，提高连读效率】
                    if self.mergeContinuousFlag:
                        contentRawArr = getSliceChunkArr(contentRawArr, self.pollingSize)
                        contentReadArr = getSliceChunkArr(contentReadArr, self.pollingSize)
                    else:
                        contentRawArr = getSplitArr(contentRawArr, self.pollingSize)
                        contentReadArr = getSplitArr(contentReadArr, self.pollingSize)
                    self.editableTabs.append({
                        'title': ws_name,
                        'connect485Id': self.stationAddress,
                        'connectStatus': autoLoopFlag,
                        'contentArr': contentArr,
                        'contentRawArr': contentRawArr,
                        'contentReadArr': contentReadArr,
                    })
                    self.RxTxcountMap[ws_name] = {
                        'tab485Id': self.stationAddress,
                        'sendCount': 0,
                        'receiveCount': 0,
                        'readErrCount': 0,
                        'countDown': len(contentReadArr), #每个tab页渲染节点的倒计时次数【即每个tab模块的读点次数】
                        'everyLoopCount': len(contentReadArr),
                        'connectResponse': False,
                        'connectStatus': autoLoopFlag,
                    }
                    if autoLoopFlag: self.tabAutoLoopList.append(ws_name)
                    self.disconnectedMapList[ws_name]=[]
                    self.historyResDataMap[ws_name] = {}
                    #初始设置每个tab标题下面的返回值列表为空
                    self.maxResponseIdx = len(contentReadArr) if len(contentReadArr)>self.maxResponseIdx else self.maxResponseIdx
            name_listArr=list(set(self.tabTitleList))
            if(len(self.tabTitleList) != len(name_listArr)):
                QMessageBox.warning(self, self.langData.get('warning_msg'), 'duplicate_tab_name, please_check!' )
            compareArr=list(set(self.regAddrList))
            if(len(compareArr) != len(self.regAddrList)):
                #列表推导式查找重复项
                repeatList=[n for n in self.regAddrList if self.regAddrList.count(n) > 1]
                repeatList=list(set(repeatList))
                self.dock_content.append('存在重复的点位: {}'.format(repeatList))
            self.fileNameList = []
            # self.signedAddrList = [item for sublist in list(self.showtypeListMap.values()) for item in sublist]
            self.signedAddrList = list(set(self.signedAddrList))
            for titleName in self.tabTitleList:
                fName = '{}_{}.csv'.format(QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss'), titleName)
                self.fileNameList.append(fName)
        except Exception as e:
            logger.error('--- read parameter_xlsx ERR: {}! ---'.format(e))
            QMessageBox.critical(self, self.langData.get('critical_msg'), '--- read_parameter_xlsx_ERR: {}! ---'.format(e))

    def initTabNodeList(self):
        #遍历多个tab页的信息，生成界面
        self.tw = QTabWidget(self)
        for tabContent in self.editableTabs:
            key = tabContent['title']
            itemList = tabContent['contentArr']
            headerLine = QHBoxLayout()
            checkedNode = QCheckBox(self.langData.get('common_loop'))
            checkedNode.setProperty('name', key)
            checkedNode.setChecked(tabContent['connectStatus'])
            checkedNode.toggled.connect(self.toggle_tabcheckBox)
            sendNode = QLabel('{}: 0'.format(self.langData.get('send_count')))
            receiveNode = QLabel('{}: 0'.format(self.langData.get('receive_count')))
            clearBtnNode = QPushButton(self.langData.get('clear_btn'))
            clearBtnNode.setIcon(QIcon('./icons/clear.png'))
            clearBtnNode.setProperty('name', key)
            clearBtnNode.clicked.connect(self.clearBtnClicked)
            plotBtnNode = QPushButton(self.langData.get('plot_realTime_data'), clicked=self.toggle_plotDataDialog)
            plotBtnNode.setIcon(QIcon('./icons/datawave.png'))
            plotBtnNode.setEnabled(tabContent['connectStatus'])
            sendNode.setProperty('name', '{}_send'.format(key))
            receiveNode.setProperty('name', '{}_receive'.format(key))
            self.RxTxNodeMap[key] = []
            self.RxTxNodeMap[key].append(sendNode)
            self.RxTxNodeMap[key].append(receiveNode)
            checkedNode.setStyleSheet('min-width:100px;margin-left:20px;')
            self.checkNodeList.append(checkedNode)
            # sendNode.setStyleSheet('min-width:90px;') # receiveNode.setStyleSheet('min-width:90px;')
            sendNode.setFixedWidth(90)
            receiveNode.setFixedWidth(90)
            clearBtnNode.setStyleSheet('min-width:60px;')
            # 节点加入到第一行的布局中
            showNode1 = QLabel(self.langData.get('station_address'))
            showNode1.setStyleSheet('max-width:80px;')
            tabAddrNode = QLineEdit(str(tabContent['connect485Id']))
            tabAddrNode.setStyleSheet('max-width:60px;')
            tabAddrNode.setValidator(slaveAddrValidator)
            tabAddrNode.setProperty('name', key)
            # tabAddrNode.textChanged.connect(self.onTabAddrChanged)
            tabAddrNode.editingFinished.connect(self.onTabAddrEdited)
            # self.startAddrNode.textChanged.connect(self.onstartAddrChanged)
            headerLine.addWidget(showNode1)
            headerLine.addWidget(tabAddrNode)
            headerLine.addWidget(checkedNode)
            headerLine.addWidget(sendNode)
            headerLine.addWidget(receiveNode)
            headerLine.addWidget(clearBtnNode)
            headerLine.addWidget(plotBtnNode)
            # 新增界面上节点编辑使能的按钮
            self.editableListMap[key]=False
            editcheckedNode = QCheckBox('editable')
            editcheckedNode.setProperty('name', key)
            editcheckedNode.toggled.connect(self.toggle_editcheckBox)
            editcheckedNode.setStyleSheet('min-width:100px;margin-left:20px;')
            # headerLine.addWidget(editcheckedNode)
            headerLine.addStretch(1)
            headerWid = QGroupBox(self.langData.get('setting'))
            headerWid.setLayout(headerLine)
            headerWid.setStyleSheet('QCheckBox:checked{ color:green;}')
            # 添加多语言的节点到列表中去
            self.langNodeMap[key] = []
            self.langNodeMap[key].append(showNode1)
            self.langNodeMap[key].append(checkedNode)
            self.langNodeMap[key].append(sendNode)
            self.langNodeMap[key].append(receiveNode)
            self.langNodeMap[key].append(clearBtnNode)
            self.langNodeMap[key].append(plotBtnNode)
            self.langNodeMap[key].append(headerWid)
            # headerWid.setFixedHeight(55) #设置固定的高度
            vlayout = QVBoxLayout()
            vlayout.addWidget(headerWid)
            # 开始UI界面的tab分区域的部分
            groupBoxList = [ QGroupBox(str(item['name'])) for item in itemList if (not 'addr' in item)]
            groupBoxList.insert(0, QGroupBox() )
            self.globlaBoxNodeMap[key] = [headerWid]
            node_count=0
            tabNodeGrid = QGridLayout()
            tabNodeGrid.setVerticalSpacing(5)
            self.regItemNodeMap[key] = []
            self.regItemNameMap[key] = []
            self.saveAllLoopArrMap[key] = []
            for item in itemList:
                if (not 'addr' in item) and len(groupBoxList)>0:
                    seperate_box=groupBoxList.pop(0)
                    seperate_box.setCheckable(True)
                    seperate_box.toggled.connect(self.expandGroupbox)
                    self.globlaBoxNodeMap[key].append(seperate_box)
                    if node_count>0:
                        # 当不足塞满一行时,设置空节点站位保持界面对齐
                        while(tabNodeGrid.columnCount() < self.columnNum):
                            emptyNode1 = QLabel('')
                            emptyNode1.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
                            tabNodeGrid.addWidget(emptyNode1, int(node_count/self.columnNum), int(node_count%self.columnNum))
                            node_count+=1
                            emptyNode2 = QLabel('')
                            tabNodeGrid.addWidget(emptyNode2, int(node_count/self.columnNum), int(node_count%self.columnNum))
                            node_count+=1
                            emptyNode3 = QLabel('')
                            emptyNode2.setFixedWidth(80)
                            emptyNode3.setFixedWidth(40)
                            tabNodeGrid.addWidget(emptyNode3, int(node_count/self.columnNum), int(node_count%self.columnNum))
                            node_count+=1
                            midWid = QWidget()
                            midWid.setLayout(tabNodeGrid)
                            midWid.setObjectName('middleWidName')
                            midLayout = QVBoxLayout()
                            midLayout.addWidget(midWid)
                            seperate_box.setLayout(midLayout)
                            vlayout.addWidget(seperate_box)
                            tabNodeGrid = QGridLayout()
                            tabNodeGrid.setVerticalSpacing(5)
                            node_count=0
                            continue
                # 1、先添加label标签===
                labelNode = EditableLabel(str(item['name']),self)
                labelNode.setProperty('label_node_count', node_count)
                if item['dataSource']:
                    labelNode.setToolTip(' {} | {} | {}'.format(item['addr'], '0X{}'.format(hex(int(item['addr']))[2:].upper().zfill(4)), item['dataSource']))
                else:
                    labelNode.setToolTip(' {} | {}'.format(item['addr'], '0X{}'.format(hex(int(item['addr']))[2:].upper().zfill(4))))
                labelNode.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
                # if item['attr']=='WO': labelNode.setStyleSheet('text-decoration:underline;')
                if item['showType']=='BUTTONS':
                    # 列数不够,没对齐,就要另起一行
                    offset_count = self.columnNum - (node_count%self.columnNum)
                    # 当不足塞满一行时,设置空节点站位保持界面对齐
                    # while((offset_count>2) and (offset_count<…   【原文损坏·被 HTML 吞掉】此处起至 SELECT/SWITCHS 分支开头的原代码丢失
                # 【推断·重建】以下 SELECT/SWITCHS 分支的开头，依据残留片段 `max_text_len else max_text_len ... selectOptionsMap[...] = itemObj` 还原
                if item['showType'] in ['SELECT', 'SWITCHS']:
                    itemObj = {}
                    max_text_len = 0
                    for i,opt in enumerate(item['options']):
                        itemObj[opt[0]] = opt[1]
                        max_text_len = len(opt[1]) if len(opt[1]) > max_text_len else max_text_len
                    self.selectOptionsMap['{}_{}'.format(item['name'], item['addr'])] = itemObj
                    selectNode=QComboBox()
                    selectNode.activated[str].connect(self.selectOneItem)
                    if item['attr']=='WO':
                        selectNode.setStyleSheet('border:1px solid #FFA500;')
                    if item['attr']=='RO':
                        selectNode.setEnabled(False) # else:
                    # 设置下拉框展开后的自适应宽度 # if max_text_len * 13 > 80: # selectNode.view().setFixedWidth(max_text_len * 13) # if len(item['options']) > 10: # # selectNode.setMaxVisibleItems(20) #设置视图内最大显示条目数 # selectNode.setStyleSheet(""" # QScrollBar:vertical { background:#fff; width: 6px;} # QScrollBar::handle {background: #ccc; } # QScrollBar::handle::hover { background: #aaa} # """)
                    tabNodeGrid.addWidget(selectNode, int(node_count/self.columnNum), int(node_count%self.columnNum))
                    self.allItemNodeList.append(selectNode)
                    self.regItemNodeMap[key].append(selectNode)
                    self.regItemNameMap[key].append(item['name'])
                else:
                    inputNode = QLineEdit()
                    inputNode.setFixedWidth(80)
                    inputNode.setProperty('attributes', item)
                    if item['attr']=='WO':
                        inputNode.setStyleSheet('border:1px solid #FFA500;')
                    if item['attr']=='RO':
                        inputNode.setDisabled(True)
                        # inputNode.setReadOnly(True)
                        # # inputNode.setStyleSheet('background:#eee;color:#000;')
                        inputNode.setFixedWidth(80)
                        if item['options']:
                            itemObj = {}
                            for i,opt in enumerate(item['options']):
                                itemObj[opt[0]] = opt[1]
                                self.selectOptionsMap[ '{}_{}'.format(item['name'], item['addr'])] = itemObj
                    if (item['showType']=='UNSIGNED' or item['showType']=='SIGNED') and item['dataSource']!='Reg32':
                        if item['precision']>0:
                            inputNode.setValidator(doubleValidator)
                        else:
                            if(item['showType']=='SIGNED'):
                                inputNode.setValidator(intValidator)
                            else:
                                inputNode.setValidator(int0_65535Validator)
                    if item['showType'] in ['DATETIME','CHARCODE','HOURMINUTE','IP','HEX'] or item['dataSource']=='Reg32':
                        #字符类型的要限制输入的长度，防止误输入
                        if item['showType']=='CHARCODE':
                            addrCount = int(item['dataSource'].replace('RegArr','')) if item['dataSource'].replace('RegArr','') else 0
                            inputNode.setMaxLength(addrCount*2)
                        if item['showType']=='HOURMINUTE':
                            inputNode.setInputMask('00:00;_') #【时分】类型的掩码
                        if item['showType']=='IP':
                            inputNode.setInputMask('000.000.000.000;_') #ip地址掩码
                            inputNode.setStyleSheet('min-width:100px;')
                            inputNode.setValidator(ipValidator)
                        if item['showType']=='DATETIME':
                            inputNode.setInputMask('0000-00-00_00:00:00') #【日期，年月日时分秒】掩码
                            inputNode.returnPressed.connect(self.keyupOtherItem)
                        else:
                            inputNode.returnPressed.connect(self.keyupOneItem)
                            # char_code——这种类型的连续占用两个节点的位置,三倍的输入框宽度[DATE_TIME]
                        if item['showType']=='CHARCODE' or item['showType']=='DATETIME':
                            tabNodeGrid.addWidget(inputNode, int(node_count/self.columnNum), int(node_count%self.columnNum), 1,4)
                            inputNode.setStyleSheet('min-width:240px;')
                            node_count+=3
                        elif item['showType']=='BUTTONS':
                            btnHbox = QHBoxLayout()
                            for i,opt in enumerate(item['options']):
                                btnNode = QPushButton(opt[1])
                                btnNode.setToolTip(opt[0])
                                btnNode.setProperty('attributes', item)
                                btnNode.setProperty('insertVal', opt[0])
                                # btnNode.setStyleSheet('padding:2px;')
                                btnNode.clicked.connect(self.btnNodeClicked)
                                btnHbox.addWidget(btnNode)
                                # self.allItemNodeList.append(btnNode) # self.regItemNodeMap[key].append(btnNode)
                            btnHbox.addWidget(QLabel(''))
                            btnHbox.addStretch(1)
                            btnWrapper = QWidget()
                            btnWrapper.setLayout(btnHbox)
                            # 列数不够,没对齐,就要计算差值并且站位，确保独占一行
                            tabNodeGrid.addWidget(btnWrapper, int(node_count/self.columnNum), int(node_count%self.columnNum), 1, self.columnNum-2)
                            node_count+= (self.columnNum-3)
                            # node_count+=3 # node_count+= btnHbox.count()
                        else:
                            tabNodeGrid.addWidget(inputNode, int(node_count/self.columnNum), int(node_count%self.columnNum))
                            self.allItemNodeList.append(inputNode)
                            self.regItemNodeMap[key].append(inputNode)
                            self.regItemNameMap[key].append(item['name'])
                            node_count+=1 #重要【节点数目记得递增】
                            # 3、最后添加unit标签
                            unitNode = QLabel(item['unit'])
                            unitNode.setFixedWidth(40)
                            tabNodeGrid.addWidget(unitNode, int(node_count/self.columnNum), int(node_count%self.columnNum))
                            node_count+=1
                            # 把最后一部分的节点加入到分区中去
            if len(groupBoxList)>0 and node_count>0:
                # 当不足塞满一行时,设置空节点站位保持界面对齐
                while(tabNodeGrid.columnCount() < self.columnNum):
                    emptyNode1 = QLabel('')
                    emptyNode1.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
                    tabNodeGrid.addWidget(emptyNode1, int(node_count/self.columnNum), int(node_count%self.columnNum))
                    node_count+=1
                    emptyNode2 = QLabel('')
                    tabNodeGrid.addWidget(emptyNode2, int(node_count/self.columnNum), int(node_count%self.columnNum))
                    node_count+=1
                    emptyNode3 = QLabel('')
                    emptyNode2.setFixedWidth(80)
                    emptyNode3.setFixedWidth(40)
                    tabNodeGrid.addWidget(emptyNode3, int(node_count/self.columnNum), int(node_count%self.columnNum))
                    node_count+=1
                seperate_box=groupBoxList[0]
                seperate_box.setCheckable(True)
                seperate_box.toggled.connect(self.expandGroupbox)
                self.globlaBoxNodeMap[key].append(seperate_box)
                midWid = QWidget()
                midWid.setLayout(tabNodeGrid)
                midWid.setObjectName('middleWidName')
                midLayout = QVBoxLayout()
                midLayout.addWidget(midWid)
                seperate_box.setLayout(midLayout)
                # seperate_box.setLayout(tabNodeGrid)
                vlayout.addWidget(seperate_box)
            wid = QWidget()
            wid.setObjectName('wid_wrapper')
            vlayout.addStretch(1)
            wid.setLayout(vlayout)
            # 1.添加到滚动区域内
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(wid)
            # 设置全局的布局
            tabwid = QWidget()
            hbox = QHBoxLayout()
            hbox.addWidget(scroll_area)
            tabwid.setLayout(hbox)
            # # 2.给这个滚动条添加属性
            scrollQss = """
                    QScrollArea{ border:1px solid #ccc;}
                    QScrollBar:horizontal { background:#fff; height:10px;}
                    QScrollBar:vertical { background:#fff; width:10px;}
                    QScrollBar::handle:horizontal {background: #ccc; }
                    QScrollBar::handle:vertical {background: #ccc; }
                    QScrollBar::handle::hover { background: #aaa}
                    # QScrollBar::handle::pressed { background: #000}
                """
            tabwid.setStyleSheet(scrollQss)
            wid.setStyleSheet('QWidget#wid_wrapper{ background:#fff;}QGroupBox::indicator{ width:12px; height:12px;}QGroupBox::indicator:checked { image: url(./icons/expand.png);}QGroupBox::indicator:unchecked { image: url(./icons/noExpand.png);}')
            tab_index = self.tw.addTab(tabwid, key)
            # 设置初始的连接状态图标
            self.tw.setTabIcon(tab_index, QIcon('./icons/disconnect.png'))
        # 把所有的tab放到设置全局中去 # self.tw.setTabVisible(self.tw.count()-1, False)
        # #默认设置为隐藏，切换的时候再打开显示
        self.tw.setStyleSheet("QTabWidget::pane{ padding:-10px -10px -9px -10px;}")
        self.setCentralWidget(self.tw)
        #最后一步设置全局的轮询点位列表
        self.latestDataMap = ['']*len(self.allItemNodeList)
        # self.setGlobalBoxDisabled(True) #[20241028]默认全局的tab页内部节点禁用，只有输入对应的密码使能

    def expandGroupbox(self):
        node = self.sender()
        # 根据点击对象找到对应的子节点，再展开收缩子节点达到效果
        currentMiddleNode = node.findChild(QWidget, 'middleWidName')
        if node.isChecked():
            currentMiddleNode.show()
        else:
            currentMiddleNode.hide()

    def replaceLabelNode(self, row=1,col=0):
        nodetext=self.sender().text()
        parentLayout = find_parent_layout(self.sender())
        parentLayout.removeWidget(self.sender())
        self.sender().deleteLater()
        labelNode = EditableLabel(nodetext, self)
        labelNode.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        parentLayout.addWidget(labelNode, row, col)

    def toggle_editcheckBox(self, state):
        node = self.sender()
        name = node.property('name')
        self.editableListMap[name]=state

    def clearBtnClicked(self):
        self.setInitGroupAddrList()
        node = self.sender()
        name = node.property('name')
        if name in self.RxTxcountMap:
            self.RxTxcountMap[name]['sendCount']=0
            self.RxTxcountMap[name]['receiveCount']=0
            txNode = self.RxTxNodeMap[name][0]
            txNode.setText('{}: 0'.format(self.langData.get('send_count')))
            rxNode = self.RxTxNodeMap[name][1]
            rxNode.setText('{}: 0'.format(self.langData.get('receive_count')))

    def toggle_tabcheckBox(self):
        node = self.sender()
        for (index, tabContent) in enumerate(self.editableTabs):
            if tabContent['title'] == node.property('name'):
                tabContent['connectStatus'] = node.isChecked()
                clist = self.langNodeMap[tabContent['title']]
                clist[5].setEnabled(node.isChecked())
                #调试方便临时注释
                if not node.isChecked():
                    self.tw.setTabIcon(index, QIcon('./icons/disconnect.png'))
                    self.RxTxcountMap[tabContent['title']]['connectResponse'] = False
                    if tabContent['title'] == self.readRegTitle:
                        self.readRegTitle = '' #把当前轮询的标题重置为空【控制tab左上角连接状态的显示，重要】，
                        break
                self.setGroupAddrList(node.isChecked())
                self.updateParameterFile(node)

    def updateParameterFile(self, node):
        tab_title = node.property('name')
        loopState = node.isChecked()
        try:
            self.fData.ws(ws= tab_title).update_index(row=1, col=2, val='autoLoop' if loopState else '')
            # 需要先移除，否则写入失败报错
            if os.path.exists('./config/parameter.xlsx'): os.remove('./config/parameter.xlsx')
            xl.writexl(db= self.fData, fn='./config/parameter.xlsx')
        except Exception as e:
            logger.error('--- reSave parameter_xlsx ERR: {}! ---'.format(e))
            return CustomToast( '--- reSave_parameter_xlsx_ERR: {}! ---'.format(e), timeout=5000)

    def onTabAddrEdited(self):
        node = self.sender()
        address_val = node.text()
        tab_title = node.property('name')
        node.clearFocus()
        # 改动地址后记得状态重置为断链
        self.RxTxcountMap[tab_title]['connectResponse'] = False
        try:
            self.fData.ws(ws= tab_title).update_index(row=1, col=1, val='connectId:{}'.format(address_val))
            # 需要先移除，否则写入失败报错
            if os.path.exists('./config/parameter.xlsx'): os.remove('./config/parameter.xlsx')
            xl.writexl(db= self.fData, fn='./config/parameter.xlsx')
        except Exception as e:
            logger.error('--- reSave parameter_xlsx ERR: {}! ---'.format(e))
            return CustomToast( '--- reSave_parameter_xlsx_ERR: {}! ---'.format(e), timeout=5000)
        # 发生变化了就重置一下界面上的全局点位的通信地址,然后再设置点位['item485Id]
        for tabContent in self.editableTabs:
            if tabContent['title']==tab_title:
                tabContent['connect485Id']=address_val
                self.RxTxcountMap[tab_title]['tab485Id']=address_val
                break
        for itemNode in self.regItemNodeMap[tab_title]:
            itemMap = itemNode.property('attributes')
            itemMap['item485Id']=address_val
            itemNode.setProperty('attributes', itemMap)
        self.setGroupAddrList(False) # 最后一步设置全局的轮询点位列表

    def setGroupAddrList(self, boolStatus):
        statusFlagList = []
        self.groupAddrList = []
        for tab in self.editableTabs:
            statusFlagList.append(tab['connectStatus'])
            # 被勾选的才会加入到列表中去【读点列表和渲染节点列表】
            if tab['connectStatus']:
                for splitArr in tab['contentReadArr']:
                    self.groupAddrList.append({
                        'addr': splitArr[0],
                        'count': len(splitArr),
                        'title': tab['title'],
                        'connect485Id': tab['connect485Id'],
                    })
        # vals = [True, False, True, True, True]
        # any(vals) # 如果任何一个为True，返回True
        # all(vals) # 如果所有的都为True，才返回True
        self.startAllTabFlag = all(statusFlagList)
        self.stopAllTabFlag = not any(statusFlagList)
        if boolStatus and self.serialCom.isOpen():
            self.historyData = b''
            self.loopOneRead()
            self.globalStatus.setText(self.langData.get('connecting'))

    def setInitGroupAddrList(self):
        # 设置初始的全局点位【包括只读N次的点位】
        self.limitedReadTimes = 0
        self.readOnceArr = copy.deepcopy(self.readOnceArrCopy)
        self.readTimesMap = copy.deepcopy(self.readTimesMapCopy)
        self.groupAddrList = []
        for tab in self.editableTabs:
            if tab['connectStatus']:
                for splitArr in tab['contentRawArr']:
                    self.groupAddrList.append({
                        'addr': splitArr[0],
                        'count': len(splitArr),
                        'title': tab['title'],
                        'connect485Id': tab['connect485Id'],
                    })

    def onstartAddrChanged(self):
        self.debounceTimer.start(1000)

    def initStartAddrText(self):
        self.debounceTimer.stop()
        self.startAddrNode.clearFocus()
        if not self.startAddrNode.text():
            return CustomToast('input_is_required, please_check!')
        addr = int(self.startAddrNode.text(),16) if self.rwHexNode.isChecked() else int(self.startAddrNode.text())
        count = int(self.startCountNode.currentText())
        self.renderGridList(addr,count)

    def startAddrEdited(self):
        node = self.sender()
        node.clearFocus()
        addr = int(self.startAddrNode.text(),16) if self.rwHexNode.isChecked() else int(self.startAddrNode.text())
        count = int(self.startCountNode.currentText())
        self.renderGridList(addr,count)

    def startCountChanged(self):
        if not self.startAddrNode.text():
            return CustomToast( 'input_is_required, please_check!')
        addr = int(self.startAddrNode.text(),16) if self.rwHexNode.isChecked() else int(self.startAddrNode.text())
        count = int(self.startCountNode.currentText())
        self.renderGridList(addr,count)

    def renderGridList(self, addr, count):
        # 先删除清空原有的条目
        item_list = list(range(self.readWriteGrid.count()))
        item_list.reverse()# 倒序删除，避免影响布局顺序
        for i in item_list:
            item = self.readWriteGrid.itemAt(i)
            self.readWriteGrid.removeItem(item)
            if item.widget():
                item.widget().deleteLater()
        rw_column_Num = 8
        rw_node_count = 0
        self.rwNodeList = []
        self.labelNodeList = []
        for idx in range(count):
            labelNode = QLabel(str(addr + idx))
            labelNode.setFixedWidth(80)
            labelNode.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.readWriteGrid.addWidget(labelNode, int(rw_node_count/rw_column_Num), int(rw_node_count%rw_column_Num))
            self.labelNodeList.append(labelNode)
            rw_node_count+=1
            inputNode = QLineEdit('0')
            inputNode.setFixedWidth(80)
            inputNode.setValidator(int0_65535Validator)
            inputNode.setProperty('address', str(addr + idx))
            inputNode.returnPressed.connect(self.keyupSingleItem)
            self.readWriteGrid.addWidget(inputNode, int(rw_node_count/rw_column_Num), int(rw_node_count%rw_column_Num))
            self.rwNodeList.append(inputNode)
            rw_node_count+=1
            self.readWriteGrid.setRowStretch(self.readWriteGrid.rowCount(), 1)
            self.readWriteGrid.setColumnStretch(self.readWriteGrid.columnCount(), 1)

    def toggle_hexBox(self, state):
        if state:
            self.startAddrNode.setValidator(hexValidator)
        else:
            self.startAddrNode.setValidator(int0_65535Validator)

    def readBtnClicked(self):
        if not self.startAddrNode.text().strip() or not self.rwStationNode.text().strip():
            return CustomToast( 'input_is_required, please_check!', color='red')
        addr = int(self.startAddrNode.text(),16) if self.rwHexNode.isChecked() else int(self.startAddrNode.text())
        count = int(self.startCountNode.currentText())
        self.statusBar.showMessage('=== insert_read: addr: {}, cnt: {} ==='.format(addr, count), 3000)
        self.readRegAddr = addr
        self.readRegCount = count
        self.edgeNumber = 5 + count *2
        self.insertReadFlag = True
        readBuffer = getreadcrc(int(self.rwStationNode.text().strip()), addr, count)
        self.delayTimer.singleShot(100,lambda: self.insertReadList(readBuffer) )

    def insertReadList(self, readByte):
        self.historyData = b''
        self.Com_Send_Data(readByte)

    def writeBtnClicked(self):
        if not self.startAddrNode.text().strip() or not self.rwStationNode.text().strip():
            return CustomToast( 'input_is_required, please_check!')
        addr = int(self.startAddrNode.text(),16) if self.rwHexNode.isChecked() else int(self.startAddrNode.text())
        vals = [int(node.text()) if node.text() else 0 for node in self.rwNodeList]
        self.writeBuffer = getwriteMulticrc(int(self.rwStationNode.text().strip()), addr, vals)
        self.edgeNumber = 8 # 写入多个值，正确的返回长度为8
        self.writeRegVal = vals
        self.writeRegAddr = addr
        self.writeRegName = addr
        self.insertWriteFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(200,lambda: self.insertWriteOne(self.writeBuffer) )

    def keyupSingleItem(self):
        currentNode = self.sender()
        addr = int(currentNode.property('address'))
        currentValue = int(float(currentNode.text()))
        if currentValue<0 or currentValue>65535:
            return CustomToast( 'input_overflow: {}, please_check!'.format(currentValue))
        self.writeBuffer = getwritecrc(int(self.rwStationNode.text().strip()), addr, currentValue)
        self.edgeNumber = len(self.writeBuffer)
        self.writeRegVal = currentValue
        self.writeRegAddr = addr
        self.writeRegName = addr
        self.insertWriteFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
        currentNode.clearFocus() #设置输入框自动失去焦点 # 下拉框触发事件

    def selectOneItem(self):
        currentNode = self.sender()
        itemMap = currentNode.property('attributes')
        if currentNode.currentData() is None:
            currentNode.clearFocus()
            return
        currentValue = int(currentNode.currentData())
        addr = int(itemMap['addr'])
        if itemMap['dataSource'].startswith('RegBit') and itemMap['bitslice'] !='':
            rawBinary = self.rawBinaryMap[addr] if addr in self.rawBinaryMap else ''
            binVal = replaceStrByIndexs(rawBinary, itemMap['bitslice'], currentValue)
            currentValue = int(str(binVal), 2)
            self.writeBuffer = getwritecrc(itemMap['item485Id'], addr, currentValue)
            self.edgeNumber = len(self.writeBuffer)
            self.writeRegVal = currentValue
            self.writeRegName = itemMap['name']
            self.writeRegAddr = addr
            self.insertWriteFlag = True
            self.send_time.stop()
            self.timerIdx = 0
            self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
            currentNode.clearFocus() #设置输入框自动失去焦点
            self.delayUpdateNode = currentNode #特殊类型的输入值的写入方法：比如IP或者HEX等

    def keyupOtherItem(self):
        currentNode = self.sender()
        itemMap = currentNode.property('attributes')
        if itemMap['showType']=='IP':
            vals = [int(x) for x in currentNode.text().split('.') if x]
            if len(vals)!=4:
                return CustomToast(self.langData.get('input_err_check_msg')+': {}'.format(vals))
            vals = [(vals[0]<<8 | vals[1]), (vals[2]<<8 | vals[3])]
        elif itemMap['showType']=='HOURMINUTE':
            vals = re.findall("\d+", currentNode.text())
            vals = [str(nx).zfill(2) for nx in vals]
            if len(vals)!=2 or int(vals[0])>24 or int(vals[1])>60:
                return CustomToast(self.langData.get('input_err_check_msg')+': {}'.format(vals))
            intHour = int(vals[0],16)
            intMinute = int(vals[1],16)
            vals = [intHour<<8 | intMinute]
        elif itemMap['showType']=='DATETIME':
            vals = re.findall("\d+", currentNode.text())
            vals = [str(nx).zfill(2) for nx in vals]
            if len(vals)!=6:
                return CustomToast(self.langData.get('input_err_check_msg')+': {}'.format(vals))
            intYear = int(vals[0])
            intMonth = int(vals[1])
            intDate = int(vals[2])
            intHour = int(vals[3])
            intMinute = int(vals[4])
            intSecond = int(vals[5])
            # intWeek = int(vals[6])
            if intMonth>12 or intDate>31 or intHour>24 or intMinute>60 or intSecond>60:
                return CustomToast(self.langData.get('input_err_check_msg')+': {}'.format(vals))
            vals = [int(vals[0],16), int('{}{}'.format(vals[1],vals[2]),16), int('{}{}'.format(vals[3],vals[4]),16), int('{}{}'.format(vals[5], '00'),16)]
        elif itemMap['showType'] == 'CHARCODE':
            splitChunk = [ord(x) for x in list(currentNode.text())]
            addrCount = int(itemMap['dataSource'].replace('RegArr','')) if itemMap['dataSource'].replace('RegArr','') else 0
            while(len(splitChunk) < addrCount*2):
                splitChunk.append(0)
            vals = [( int(splitChunk[i])<<8 | int(splitChunk[i+1])) for i in range( 0, len(splitChunk), 2 )]
        elif itemMap['showType'] == 'HEX':
            # 匹配输入的只能是16进制的符号
            pattern = r'([A-Fa-f0-9])'
            vals = ''.join(re.findall(pattern, currentNode.text()))
            if len(vals) >4:
                self.statusBar.showMessage('输入长度有误: {}, 请检查!'.format(vals), 3000)
                return CustomToast(self.langData.get('input_err_check_msg') )
            vals = [int(vals, 16)]
        if itemMap['dataSource']=='Reg32':
            # 用于将输入的十进制数转换成十六进制,然后反转拆分成四个字节，每两个字节为一个点位的值
            formatHexStr = ''.join(re.findall('(.{2})', struct.pack('i', int(currentNode.text())).hex())[::-1])
            vals = [int(n, 16) for n in re.findall('(.{4})', formatHexStr)]
        else:
            addrCount = int(itemMap['dataSource'].replace('RegArr','')) if itemMap['dataSource'].replace('RegArr','') else ''
            if addrCount and addrCount != len(vals):
                self.statusBar.showMessage('输入长度有误: {}, 请检查!'.format(vals), 3000)
                return CustomToast(self.langData.get('input_err_check_msg') )
        addr = int(itemMap['addr'])
        self.writeBuffer = getwriteMulticrc(itemMap['item485Id'], addr, vals)
        self.edgeNumber = 8 # 写入多个值，正确的返回长度为8
        self.writeRegName = itemMap['name']
        self.writeRegAddr = addr
        self.writeRegVal = vals
        self.insertWriteFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
        currentNode.clearFocus()
        self.delayUpdateNode = currentNode

    def keyupOneItem(self):
        currentNode = self.sender()
        # if currentNode.isModified() is False: # return #文本未改变就不要触发写入事件
        itemMap = currentNode.property('attributes')
        addr = int(itemMap['addr'])
        if itemMap['precision']>0:
            currentValue = int(float(currentNode.text()) *math.pow(10, itemMap['precision']))
        else:
            currentValue = int(float(currentNode.text()))
        if itemMap['dataSource'].startswith('RegBit') and itemMap['bitslice'] !='':
            rawBinary = self.rawBinaryMap[addr] if addr in self.rawBinaryMap else ''
            binVal = replaceStrByIndexs(rawBinary, itemMap['bitslice'], currentValue)
            currentValue = int(str(binVal), 2)
        if itemMap['showType'] == 'SIGNED':
            currentValue = (currentValue + 65536) if currentValue <0 else currentValue
            if currentValue<0 or currentValue>65535:
                return CustomToast( 'input_overflow: {}, please_check!'.format(currentValue))
        self.writeBuffer = getwritecrc(itemMap['item485Id'], addr, currentValue)
        self.edgeNumber = len(self.writeBuffer)
        self.writeRegVal = currentValue
        self.writeRegAddr = addr
        self.writeRegName = itemMap['name']
        self.insertWriteFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
        currentNode.clearFocus() #设置输入框自动失去焦点
        self.delayUpdateNode = currentNode

    def switchNodeClicked(self, switchFlag):
        currentNode = self.sender()
        itemMap = currentNode.property('attributes')
        itemObj = {}
        toggleList = []
        for opt in itemMap['options']:
            itemObj[opt[1]] = opt[0]
            toggleList.append(opt[1])
        toggleText = toggleList[1] if switchFlag else toggleList[0]
        addr = int(itemMap['addr'])
        currentValue = int(itemObj[toggleText])
        currentNode.setProperty('text', itemObj[toggleText])
        if itemMap['dataSource'].startswith('RegBit') and itemMap['bitslice'] !='':
            rawBinary = self.rawBinaryMap[addr] if addr in self.rawBinaryMap else ''
            binVal = replaceStrByIndexs(rawBinary, itemMap['bitslice'], currentValue)
            currentValue = int(str(binVal), 2)
        self.writeBuffer = getwritecrc(itemMap['item485Id'], addr, currentValue)
        self.edgeNumber = len(self.writeBuffer)
        self.writeRegVal = currentValue
        self.writeRegName = itemMap['name']
        self.writeRegAddr = addr
        self.insertWriteFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
        currentNode.clearFocus() #设置输入框自动失去焦点
        self.delayUpdateNode = currentNode

    def btnNodeClicked(self):
        currentNode = self.sender()
        itemMap = currentNode.property('attributes')
        currentValue = int(currentNode.property('insertVal'))
        addr = int(itemMap['addr'])
        if itemMap['dataSource'].startswith('RegBit') and itemMap['bitslice'] !='':
            rawBinary = self.rawBinaryMap[addr] if addr in self.rawBinaryMap else ''
            binVal = replaceStrByIndexs(rawBinary, itemMap['bitslice'], currentValue)
            currentValue = int(str(binVal), 2)
        if itemMap['showType'] == 'SIGNED':
            currentValue = (currentValue + 65536) if currentValue <0 else currentValue
            if currentValue<0 or currentValue>65535:
                return CustomToast( 'input_overflow: {}, please_check!'.format(currentValue))
        citem485Id = self.RxTxcountMap[itemMap['tabTitle']]['tab485Id']
        self.writeBuffer = getwritecrc(citem485Id, addr, currentValue)
        self.edgeNumber = len(self.writeBuffer)
        self.writeRegName = itemMap['name']
        self.writeRegVal = currentValue
        self.writeRegAddr = addr
        self.insertWriteFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
        currentNode.clearFocus() #设置输入框自动失去焦点

    def insertWriteOne(self, writeByte):
        self.historyData = b''
        self.Com_Send_Data(writeByte)

    def open_otaDialog(self):
        if int(self.passwordLabel.text())<3:
            return CustomToast('密码等级权限不够,请检查!')
        # 延迟0.5秒钟再切换到OTA模式，避免接收到错误的报文
        self.execDelayTimer.singleShot(500, self.otaDialogOpenedTrigger)
        otaDialog.show()
        otaDialog.raise_()

    def otaDialogOpenedTrigger(self):
        self.send_time.stop()
        self.otaDialogOpened = True #OTA窗口打开的标记、
        self.historyData = b'' #历史报文清零
        self.updateIndex=0
        self.otaCurrentCount = 3
        self.devSNnode.setText('')
        self.devVersionnode.setText('')
        self.updateTiptext.setText('')
        self.devInputNode.setEnabled(True)
        self.otaUpdateList.setEnabled(True)
        self.byteLenInputNode.setEnabled(True)
        self.updateTriggerBtn.setEnabled(True)

    def open_dataRWDialog(self):
        if int(self.passwordLabel.text())<3:
            return CustomToast('密码等级权限不够,请检查!')
        dataRWDialog.show()
        dataRWDialog.raise_()

    def open_faultLogDialog(self):
        if int(self.passwordLabel.text())<3:
            return CustomToast('密码等级权限不够,请检查!')
        # 延迟0.5秒钟再切换到文件上传模式，避免接收到错误的报文
        self.execDelayTimer.singleShot(500, self.logDialogOpenedTrigger)
        self.initFileLogParams()
        faultLogDialog.show()
        faultLogDialog.move(self.geometry().left(), self.geometry().top()) # 设置对话框的位置 faultLogDialog.raise_()

    def logDialogOpenedTrigger(self):
        self.send_time.stop()
        self.logDialogOpened = True #log窗口打开的标记、
        self.historyData = b'' #历史报文清零 # 切换 实时数据波形界面 的可见状态

    def toggle_plotDataDialog(self):
        if plotMonitorDialog.isVisible():
            return
        if self.serialCom.isOpen() and not self.send_time.isActive() and self.toggle_plotGraphFlag2:
            self.dock_content.append('===looptimer_NOTActive===')
            self.send_time.start(100)
            self.plotGraphType = 'datawave'
            plotMonitorDialog.show()
            plotMonitorDialog.move(self.geometry().left(), self.geometry().top())
            # 设置对话框的位置
            if self.toggle_plotGraphFlag2 and len(self.monitorCurveList)>0:
                self.plotMonitorGraphFlag = True # 切换 软件示波器弹框 的可见状态

    def toggle_plotSoftDataDialog(self, state):
        if plotWidDialog.isVisible(): return
        if self.send_time.isActive():
            self.dock_content.append('===looptimer_isActive===')
            self.send_time.stop() #开始软件示波器之前,先关掉常规轮询的定时器
            self.plotGraphType = 'softwave'
            plotWidDialog.show()
            plotWidDialog.move(self.geometry().left(), self.geometry().top())
            # 设置对话框的位置
            if not self.plotWidDialogIsVisited:
                self.initMemoryList()
                self.toggle_plotGraph()
                #默认调用打开波形按钮的方法
                self.selectModeType()
                self.selectDataType()
                self.selectTriggerType()
                self.plotWidDialogIsVisited=True

    def initMemoryList(self):
        if self.dataTypeList.currentIndex()==0:
            self.selectedChannelMap = []
            for nx,name in enumerate(self.checkedChannelList):
                self.selectedChannelMap.append({
                    'name': name,
                    'addr': '',
                    'color': self.regColorList[nx],
                    'scale': str(self.regScaleList[nx]),
                    'offset': str(self.regOffsetList[nx]),
                })
        if self.dataTypeList.currentIndex()==1:
            if len(self.uuidBinaryMap)>0:
                self.selectedChannelMap = []
                currentselectedChannel = list(self.channelAddrInfoMap.keys())
                for (key,uuid) in enumerate(currentselectedChannel):
                    if self.channelAddrRawMap.get(uuid, {}).get('checked','')!='Y': continue
                    self.selectedChannelMap.append({
                        'uuid': uuid,
                        'addr': self.channelAddrRawMap.get(uuid, {}).get('addr',''),
                        'name': self.channelAddrRawMap.get(uuid, {}).get('name',''),
                        'color': self.regColorList[key],
                        'scale': self.regScaleList[key],
                        'offset': self.regOffsetList[key],
                    })

    def open_bufferDialog(self):
        bufferDialog.show()
        bufferDialog.move(self.geometry().left(), self.geometry().top())
        # 设置对话框的位置
        bufferDialog.raise_()
        # 打开弹框的时候也打开报文的勾选框
        self.toggle_text.setChecked(True)

    # 串口open按钮按下
    def Com_Toggle_Button_clicked(self, toggleType):
        self.insertWriteFlag = False
        self.loopReadFlag = False
        self.loopWriteFlag = False
        self.loopWriteBatchFlag = False
        self.latestTimeStamp = round(time.time()*1000)
        self.setInitGroupAddrList()
        if self.disconnectedTimer.isActive(): self.disconnectedTimer.stop()
        if self.serialCom.isOpen():
            self.send_time.stop()
            self.serialCom.close()
            self.serialPortList.setEnabled(True)
            self.baudRateList.setEnabled(True)
            self.globalStatus.setText(self.langData.get('port_closed'))
            self.key_text_toggle.setText(self.langData.get('open_port'))
            if self.toggle_text.isChecked():
                self.rightList.appendToBottom('=== {} 串口已关闭! ==='.format( getCurrentStamp()))
                self.saveLoopDataFile()
                self.saveBufferListItem()
        else:
            comName = self.serialPortList.currentText()
            comBaud = int(self.baudRateList.currentText())
            self.currentComName = self.serialPortList.currentText()
            self.serialCom.setPortName(comName)
            self.serialCom.setBaudRate(comBaud)
            try:
                if self.serialCom.open(QSerialPort.ReadWrite) == False:
                    if toggleType=='autoToggle':
                        self.dock_content.append('open_failed!')
                        self.serialPortList.setEnabled(True)
                        self.baudRateList.setEnabled(True)
                        self.globalStatus.setText(self.langData.get('port_closed'))
                        self.key_text_toggle.setText(self.langData.get('open_port'))
                        if self.toggle_text.isChecked(): self.rightList.appendToBottom('=== {} 串口打开失败! ==='.format( getCurrentStamp()))
                    else:
                        QMessageBox.critical(self, self.langData.get('critical_msg'), self.langData.get('serialport_open_failed') )
                        return
                else:
                    self.serialPortList.setEnabled(False)
                    self.baudRateList.setEnabled(False)
                    self.globalStatus.setText(self.langData.get('port_opened'))
                    self.key_text_toggle.setText(self.langData.get('close_port'))
                    #将信息写入CFG中存储，便于下次使用
                    self.configSettingMap['comName']=comName
                    self.configSettingMap['comBaud']=str(comBaud)
                    if self.toggle_text.isChecked(): self.rightList.appendToBottom('=== {} 串口已打开! ==='.format( getCurrentStamp()))
                    # 打开串口默认就开始轮询数据了20231228
                    self.exportDateTimeLimit = time.time() + self.autoSaveInterval
                    self.historyData = b''
                    self.loopOneRead()
                    if self.listenerChk.isChecked(): self.disconnectedTimer.start(1000)
            except Exception as e:
                if toggleType=='autoToggle':
                    logger.error('open_failed!:', e)
                    self.serialPortList.setEnabled(True)
                    self.baudRateList.setEnabled(True)
                    self.globalStatus.setText(self.langData.get('port_closed'))
                    self.key_text_toggle.setText(self.langData.get('open_port'))
                else:
                    QMessageBox.critical(self, self.langData.get('critical_msg'), '{} {}'.format(self.langData.get('serialport_open_failed'), e))
                    #设置全局的tab页的连接状态
                    self.resetTabStatus()

    # 初始化串口列表
    def initSerialPortList(self):
        self.serialCom = QSerialPort()
        self.serialCom.readyRead.connect(self.Com_Receive_Data) # 接收数据
        self.refreshPort()

    def custom_sort_key(self,s):
        # 使用正则表达式将字符串中的数字和非数字部分分开
        parts = re.split('(\d+)', s)
        # 将数字部分转换为整数，非数字部分保持不变
        parts = [int(part) if part.isdigit() else part for part in parts]
        return parts

    def refreshPort(self):
        # 串口刷新
        if self.serialPortList.isEnabled():
            self.serialPortList.clear()
            com_list = QSerialPortInfo.availablePorts()
            comName_list = [info.portName() for info in com_list]
            # 使用 sorted 函数和自定义排序键进行排序
            sorted_com_list = sorted(comName_list, key=self.custom_sort_key)
            self.serialPortList.addItems(sorted_com_list)

    def throwErrHandler(self):
        if self.receiveWriteFlag:
            self.responseTimer.stop()
            self.statusBar.showMessage('_write {}, {}, failed!!!'.format(self.writeRegName, self.writeRegVal), 3000)
            self.setStatusBarColor('red')
            if self.toggle_text.isChecked():
                self.rightList.appendToBottom('{}, _rxWrongBuffer: {}, write_failed!!!'.format(getCurrentStamp(), self.historyData.hex().upper() ))
                self.saveBufferList.append('{}, _rxWrongBuffer: {}, write_failed!!!'.format(getCurrentStamp(), self.historyData.hex().upper() ))
            self.insertWriteFlag = False
            self.receiveWriteFlag = False
            self.send_time.stop()
            self.timerIdx = 0
            if self.alternateReadWriteFlag:
                return self.alternateExection()
            if self.serialCom.isOpen():
                self.loopOneRead()
                # 串口发送数据

    def Com_Send_Data(self, byteData):
        if not self.serialCom.isOpen():
            CustomToast(self.langData.get('serialport_not_opened_msg'))
            self.send_time.stop()
            self.timerIdx = 0
            return
        if self.insertReadFlag:
            self.receiveReadFlag = True
            if self.insertWriteFlag:
                self.receiveWriteFlag = True
                self.responseTimer.start(self.writeWaitTime)
                # 设置延时器为N毫秒；否则跑错提示
                try:
                    self.serialCom.write(byteData)
                    if self.readRegTitle and self.readRegTitle in self.RxTxcountMap:
                        self.RxTxcountMap[self.readRegTitle]['sendCount']+=1
                        # 除去常规正常轮询的，其他的读写都不会递减当前tab页的倒计时次数
                        if not self.insertReadFlag and not self.insertWriteFlag:
                            self.RxTxcountMap[self.readRegTitle]['countDown']-=1
                            txNode = self.RxTxNodeMap[self.readRegTitle][0]
                            txNode.setText('{}: {}'.format(self.langData.get('send_count'), self.RxTxcountMap[self.readRegTitle]['sendCount']))
                            self.sendIdx += len(byteData)
                            self.label_txt.setText(str(self.sendIdx))
                            if self.toggle_text.isChecked():
                                self.rightList.appendToBottom('[{}]发[{}]→ {}'.format(getCurrentStamp(), len(byteData), byteData.hex().upper()))
                                self.saveBufferList.append('[{}]发[{}]→ {}'.format(getCurrentStamp(), len(byteData),byteData.hex().upper()))
                except Exception as e:
                    self.statusBar.showMessage( '---十六进制发送错误, ERR: {}---'.format(e), 3000)
                    logger.error('---send_hex_data_err: {}---'.format(e))
                    QMessageBox.critical(self, self.langData.get('critical_msg'), '---send_hex_data_err: {}---'.format(e))

    def delayRenderText(self):
        rxDevinfoBuffer=re.findall('(.{2})', self.historyData)
        if len(self.historyData)>37:
            snList = [chr(int(nx,16)) for nx in rxDevinfoBuffer[6:37]]
            self.devSNnode.setText(''.join(snList))
            verList = [chr(int(nx,16)) for nx in rxDevinfoBuffer[38:69]]
            self.devVersionnode.setText(''.join(verList))
            self.devSNnode.setText(self.historyData[6:37].decode('utf-8'))
            self.devVersionnode.setText(self.historyData[38:69].decode('utf-8'))
            self.updateTiptext.setText(self.langData.get('read_version_success'))
        else:
            self.devSNnode.setText('')
            self.devVersionnode.setText('')
            self.updateTiptext.setText('')
            CustomToast(self.langData.get('response_fail_msg'))

    def getReadValueBuffer(self):
        if len(self.historyData) >= self.edgeNumber:
            self.listenerState='readReg'
            splitBuffer = self.historyData[0:self.edgeNumber]
            self.historyData = self.historyData[self.edgeNumber:]
            self.updateListenerData(splitBuffer)

    def getReadAddrBuffer(self):
        splitBuffer = self.historyData[0:self.readRegBufferCount]
        self.historyData = self.historyData[self.readRegBufferCount:]
        checksum = calc_byte_crc(splitBuffer[0:6])
        if splitBuffer.endswith(checksum):
            self.listenerState='readValue'
            for regTitle in self.RxTxcountMap:
                if self.RxTxcountMap[regTitle].get('tab485Id')==self.stationAddress:
                    self.readRegTitle = regTitle
                    break

    def updateWriteprogress(self):
        if (len(self.historyData) % self.edgeNumber)!=0: return
        if (self.historyData == self.writeBuffer) or (len(self.historyData)==self.edgeNumber and self.historyData[1]==0x10):
            self.statusBar.showMessage('_write {}, {}, success!'.format(self.writeRegName, self.writeRegVal), 3000)
            self.setStatusBarColor('green')
            self.responseTimer.stop()
            self.writeDataArr.append([ QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss_zzz'), self.writeRegName, self.writeRegAddr, self.writeRegVal])
            if self.toggle_text.isChecked():
                self.rightList.appendToBottom('{}, _write {}, {}, success!'.format(getCurrentStamp(), self.writeRegAddr, self.writeRegVal))
                self.saveBufferList.append('{}, _write {}, {}, success!'.format(getCurrentStamp(), self.writeRegAddr, self.writeRegVal))
            if self.alternateReadWriteFlag: return self.alternateExection()
            if self.loopWriteFlag:
                rowLine = self.regAddrLineMap.get(self.writeRegAddr, 0)
                self.dock_content.append('writelineIdx_: {}, waddr: {}, wval_: {}========='.format(rowLine, self.writeRegAddr, self.writeRegVal) )
                # 【原文损坏】updateWriteprogress 的后半段（循环写入时发送下一行的逻辑）被 HTML 吞掉，无法确认原代码
                pass

    def updateLogprogress(self):
        # 【原文整体丢失·仅据残片重建骨架】残片只剩条件表达式与四个分支调用，判断条件的细节为推断
        if len(self.historyData) < 6 or (len(self.historyData) < int.from_bytes(self.historyData[4:6], byteorder='big')) or (self.logTxBuffer[:4] != self.historyData[:4]):
            return
        self.logResponseTimer.stop()
        if self.currentFileLogType == 'getFileInfoList':
            self.delayRenderFileList()
        elif self.currentFileLogType == 'getFileRequest':
            self.delayRenderFileInfo()
        elif self.currentFileLogType == 'getFilePackage':
            self.delayRenderFileDetail()
        elif self.currentFileLogType == 'finishFileInfo':
            self.delayRenderFileFinish()

    def updateOTAprogress(self):
        # 【原文整体丢失·无法确认】OTA 升级响应的处理逻辑（0x15 的 00/01/02/03 应答校验、进度条更新）未留下任何残片
        pass

    # 串口接收数据
    def Com_Receive_Data(self):
        try:
            byteData=bytes(self.serialCom.readAll())
        except Exception as e:
            logger.error('serialport_receive_data_err: {}'.format(e))
            self.dock_content.append('serialport_receive_data_err: {}'.format(e))
        self.receiveIdx+=len(byteData)
        self.label_rxt.setText(str(self.receiveIdx))
        currentTimeStamp1=round(time.time()*1000)
        currentRXstamp=getCurrentStamp()
        if not self.receiveHexNode.isChecked():
            Data= byteData.decode('utf-8', errors='ignore')  # 【修复】原文此行被 HTML 吞噬为 `"errors="ignore""`
            if self.toggle_text.isChecked():
                if currentTimeStamp1>(self.latestTimeStamp + self.updateStampWaitTime):
                    self.rightList.append_text('[{}]收← {}'.format(currentRXstamp, Data))
                else:
                    self.rightList.append_text('{}'.format(Data))
                    self.rightList.scrollToBottom()
                self.saveBufferList.append('[{}]收[{}]← {}'.format(currentRXstamp, len(Data), Data))
                self.latestTimeStamp = currentTimeStamp1 #每次的存储一下最近一次接受的时刻的时间戳用于比较
                if len(self.saveBufferList) > self.bufferTextLen:
                    self.saveBufferListItem()
            return
        self.historyData += byteData
        if len(self.historyData) > self.historyDataMaxLen:
            self.historyData = b''
        if self.toggle_text.isChecked():
            self.rightList.appendToBottom('[{}]收[{}]← {}'.format(currentRXstamp,len(byteData), byteData.hex().upper()))
            self.saveBufferList.append('[{}]收[{}]← {}'.format(currentRXstamp, len(byteData), byteData.hex().upper()))
            if len(self.saveBufferList) > self.bufferTextLen:
                self.saveBufferListItem()
        if self.readBytesOnlyFlag: return #读字节模式下仅接受数据，不做其他处理
        if self.plotGraphType =='softwave':
            return self.updateWaveRenderData(byteData)
        if self.listenerChk.isChecked():
            if (self.receiveIdx>1) and (currentTimeStamp1 >(self.latestTimeStamp + self.updateStampWaitTime)):
                self.latestTimeStamp = currentTimeStamp1
                self.dock_content.append('===listenerChk_timeout, current_stamp: {}, historydata_:{}, Data_: {}'.format(self.latestTimeStamp, self.historyData, byteData) )
                self.statusBar.showMessage('Response_Time_Out', 3000)
                self.historyData=byteData #响应超时就给之前的历史报文清零，保留当前这一帧
                return
            self.latestTimeStamp = currentTimeStamp1
            while len(self.historyData)>=2 and self.historyData[1]!=3:
                self.historyData = self.historyData[1:]
            if self.listenerState=='readReg':
                if (len(self.historyData) >= self.readRegBufferCount) and (self.historyData[1]==3):
                    readCount = int.from_bytes(self.historyData[4:6], byteorder='big')
                    # 如果读点个数超过一般最大限值，默认这一帧是读值的数据，切换到下一个状态去
                    if 0 < readCount <= self.pollingSize:
                        self.stationAddress = self.historyData[0]
                        self.readRegAddr = int.from_bytes(self.historyData[2:4], byteorder='big')
                        self.readRegCount = readCount
                        self.edgeNumber = 5 + self.readRegCount*2
                    else:
                        self.listenerState='readValue'
                        return self.getReadAddrBuffer()
                    if len(self.historyData)>10:
                        self.getReadValueBuffer()
            elif self.listenerState=='readValue':
                if not self.readRegAddr or not self.readRegCount:
                    return self.resetListener()
                self.getReadValueBuffer()
            return
        if self.logDialogOpened: return self.updateLogprogress()
        if self.otaDialogOpened: return self.updateOTAprogress()
        if self.receiveWriteFlag: return self.updateWriteprogress()
        # 开始解析常规轮询【读值】的数据处理
        if (len(self.historyData) % self.edgeNumber) ==0:
            self.updateRenderData()
            self.historyData = b''
            self.loopIdx+=1
            self.send_time.stop()
            self.timerIdx = 0 # 获取到节点然后设置接收计数的更新
            if self.readRegTitle and self.RxTxcountMap[self.readRegTitle]:
                self.RxTxcountMap[self.readRegTitle]['receiveCount']+=1
                rxNode = self.RxTxNodeMap[self.readRegTitle][1]
                rxNode.setText('{}: {}'.format(self.langData.get('receive_count') , self.RxTxcountMap[self.readRegTitle]['receiveCount']))
                self.RxTxcountMap[self.readRegTitle]['readErrCount']=0
                # 如果有响应，某个tab之前的连接状态为【断开】就重置为连接【正常】，接收错误次数也重置为0
                if self.RxTxcountMap[self.readRegTitle]['connectResponse'] is False:
                    self.RxTxcountMap[self.readRegTitle]['connectResponse'] = True
                    self.tw.setTabIcon(self.tabTitleList.index(self.readRegTitle), QIcon('./icons/connection.png'))
                    #每次改变tab的状态,同时要更新后台保存的节点的数目
                    self.setInitGroupAddrList() #出现断链的情况，就重置【重复读点的次数】为初始值，设置全局的轮询点位为所有的点
            time.sleep(self.sleepTime)
            if self.serialCom.isOpen() and not self.insertWriteFlag and not self.insertReadFlag:
                self.loopOneRead()
        else:
            if len(self.historyData)>1 and self.historyData[1]==0x83:
                if self.receiveReadFlag:
                    self.insertReadFlag = False
                    self.receiveReadFlag = False
                    self.loopIdx-=1
                    self.responseTimer.stop()
                    self.statusBar.showMessage('_read {}, {}, failed!!!'.format(self.readRegAddr, self.readRegCount), 3000)
                    if self.toggle_text.isChecked():
                        self.rightList.appendToBottom('{}, _rxWrongBuffer: {}, read failed!!!'.format(getCurrentStamp(), self.historyData.hex().upper() ))
                        self.saveBufferList.append('{}, _rxWrongBuffer: {}, read failed!!!'.format(getCurrentStamp(), self.historyData.hex().upper() ))
                    self.insertWriteFlag = False
                    self.receiveWriteFlag = False
                    self.send_time.stop()
                    self.timerIdx = 0
                    if self.serialCom.isOpen():
                        self.loopOneRead()
    def updateRenderData(self):
        if (len(self.historyData)>1) and(self.historyData[1]==3) and checkBufferSum(self.historyData, self.readRegCount):
            splitChunk = self.historyData[3: 3+ 2* self.readRegCount]
            resVal=''
            for i in range( 0, len(splitChunk), 2 ):
                resAddr = self.readRegAddr + int(i/2)
                # resVal = int(splitChunk[i], 16)<<8 | int(splitChunk[i+1], 16)
                resVal = int.from_bytes(splitChunk[i:i+2], byteorder='big')
                if self.readRegTitle in self.historyResDataMap:
                    self.historyResDataMap[self.readRegTitle][resAddr] = resVal
                # 等吧原始数据赋值给tab页总map以后，在按照有符号做判断赋值
                if resAddr in self.signedAddrList:
                    resVal = resVal-65536 if resVal>32767 else resVal
                self.historyResData[resAddr] = resVal
                if self.alternateReadWriteFlag:
                    self.regAddrLineMap[resAddr] = resVal
                if resAddr in self.checkedAddrMap:
                    self.checkedAddrMap[resAddr] = resVal
            # 如果是插入一条读值的指令，就只渲染数据读写界面的节点
            if self.alternateReadWriteFlag:
                self.dock_content.append('Success, alterRead_: {}'.format( self.regAddrLineMap))
                return self.alternateExection()
            if self.loopReadFlag:
                self.dock_content.append('loopread_idx_:{}, _addr:{}, val_:{}'.format(self.loopReadIndex,self.readRegAddr, resVal))
                self.readDataMap[self.readRegAddr]=resVal
                # 更新表格原始值的数据
                rowLine = self.regAddrLineMap.get(self.readRegAddr, 0)
                # 【推断】原文此处 `0<=rowLine<…>` 之间的内容被 HTML 吞掉，按语义改为轮询索引是否越界
                if self.loopReadIndex >= len(self.regItemList):
                    self.loopReadIndex = 0
                    self.loopReadFlag = False
                    self.insertReadFlag = False
                    self.receiveReadFlag = False
                    self.setGroupAddrList(False)
                    savecsvBtn.setEnabled(True)
                    savepwfBtn.setEnabled(True)
                    return
            if self.receiveReadFlag:
                self.insertReadFlag = False
                self.receiveReadFlag = False
                self.loopIdx-=1
                if self.insertReadMCUFlag:
                    return self.updateReadMCUdata()
                else:
                    return self.updateReadTabData()
            try:
                if self.readRegTitle and (self.RxTxcountMap[self.readRegTitle]['countDown']<=0):
                    self.RxTxcountMap[self.readRegTitle]['countDown'] = self.RxTxcountMap[self.readRegTitle]['everyLoopCount']
                    self.regItemNodeList = self.regItemNodeMap[self.readRegTitle]
                    self.currentTabData = self.historyResDataMap[self.readRegTitle]
                    self.updateNodeData()
                if self.plotMonitorGraphFlag and self.currentTab.get('title')==self.readRegTitle:
                    self.realTime_DataPlot()
            except Exception as e:
                logger.error( '--- updateTab_NodeData_ERR: {}! ---'.format(e))
                self.statusBar.showMessage( '--- updateTab_NodeData_ERR: {}! ---'.format(e), 3000)
    def updateListenerData(self, rxFrameBuffer):
        if (rxFrameBuffer[1]==3) and checkBufferSum(rxFrameBuffer, self.readRegCount):
            if not self.readRegTitle or not self.RxTxcountMap.get(self.readRegTitle) or not (self.readRegTitle in self.historyResDataMap):
                self.dock_content.append('reg_title:{}, Not found!'.format(self.readRegTitle))
                return
            # 添加计数：统计收到的帧数，以及一个周期的轮询次数
            try:
                # setCurrentTabDisconnect[disconnectedTimer]
                if self.RxTxcountMap[self.readRegTitle]['connectResponse'] is False:
                    self.RxTxcountMap[self.readRegTitle]['connectResponse'] = True
                    self.tw.setTabIcon(self.tabTitleList.index(self.readRegTitle), QIcon('./icons/connection.png'))
                    self.RxTxcountMap[self.readRegTitle]['countDown']-=1
                    self.RxTxcountMap[self.readRegTitle]['receiveCount']+=1
                    self.disconnectedMapList[self.readRegTitle].append(self.RxTxcountMap[self.readRegTitle]['receiveCount'])
                    self.disconnectedMapList[self.readRegTitle] = self.disconnectedMapList[self.readRegTitle][-2:]
                    if self.RxTxNodeMap.get(self.readRegTitle):
                        rxNode = self.RxTxNodeMap[self.readRegTitle][1]
                        rxNode.setText('{}: {}'.format(self.langData.get('receive_count') , self.RxTxcountMap[self.readRegTitle]['receiveCount']))
                        splitChunk = rxFrameBuffer[3: 3+ 2* self.readRegCount]
                        for i in range( 0, len(splitChunk), 2 ):
                            resVal = int.from_bytes(splitChunk[i:i+2], byteorder='big')
                            resAddr = self.readRegAddr + int(i/2)
                            self.historyResData[resAddr] = resVal
                            self.historyResDataMap[self.readRegTitle][resAddr] = resVal
                        if self.RxTxcountMap[self.readRegTitle]['countDown']<=0:
                            self.RxTxcountMap[self.readRegTitle]['countDown'] = self.RxTxcountMap[self.readRegTitle]['everyLoopCount']
                            self.regItemNodeList = self.regItemNodeMap[self.readRegTitle]
                            self.currentTabData = self.historyResDataMap[self.readRegTitle]
                            self.updateNodeData()
            except Exception as e:
                logger.error( '--- listener_updateTab_NodeData_ERR: {}! ---'.format(e))
                self.statusBar.showMessage( '--- listener_updateTab_NodeData_ERR: {}! ---'.format(e), 3000)
                self.resetListener()

    def updateNodeData(self):
        # 更新界面节点数据的同时，添加到历史缓存里面。方便保存
        currentLoopArr = ['']*len(self.regItemNameMap[self.readRegTitle])
        for idx,currentNode in enumerate(self.regItemNodeList):
            if currentNode is not None and not currentNode.hasFocus():
                if self.delayUpdateNode == currentNode:
                    self.delayUpdateNode = None
                    continue #如果当前正在执行写入的操作，就跳过这次的赋值操作
            itemMap = currentNode.property('attributes')
            reg = int(itemMap['addr'])
            #先获取到当前节点所在的tab页的返回值列表【防止返回相同地址的值会混淆】，再去查找对应值
            indexValue = str(self.currentTabData.get(reg,''))
            if indexValue=='': continue
            # 针对有限次数的特殊点位:如果某个点的【读点次数】已经用完了就重置为空值，否则继续赋值
            if reg in self.readOnceArrCopy:
                if reg in self.readTimesMap: self.readTimesMap[reg] -=1
                if self.readTimesMap[reg] <=0:
                    del self.readTimesMap[reg]
                else:
                    indexValue=''
                    continue #把下拉选的值转为map方便查找
            optionMap = {}
            if itemMap['options'] and ('{}_{}'.format(itemMap['name'], itemMap['addr']) in self.selectOptionsMap):
                optionMap = self.selectOptionsMap['{}_{}'.format(itemMap['name'], itemMap['addr'])] # 开始根据数据来源来处理格式化
            if itemMap['dataSource'].startswith('RegBit'):
                [rawStr, sliceStr] = parse2bitSlice(indexValue, itemMap['bitslice'])
                self.rawBinaryMap[reg]=rawStr
                if itemMap['showType'] == 'SELECT':
                    value2label = optionMap[sliceStr] if (sliceStr in optionMap) else sliceStr
                    currentNode.setCurrentText(value2label)
                    self.latestDataMap[idx] = value2label
                    currentLoopArr[idx] = value2label
                elif itemMap['showType'] == 'SWITCHS':
                    # 如果不存在下拉选项就加入进去方便显示在界面上
                    if (sliceStr==itemMap['options'][0][0]) and (currentNode._switch_on is True): currentNode.toggleSwitch(False)
                    if (sliceStr==itemMap['options'][1][0]) and (currentNode._switch_on is False): currentNode.toggleSwitch(True)
                    value2label = optionMap[sliceStr] if (sliceStr in optionMap) else sliceStr
                    # currentNode.setToolTip(' {} | {}'.format(sliceStr, value2label))
                    self.latestDataMap[idx] = value2label
                    currentLoopArr[idx] = value2label
                else:
                    currentNode.setText(str(sliceStr))
                    self.latestDataMap[idx] = str(sliceStr)
                    currentLoopArr[idx] = str(sliceStr)
                if itemMap['highLightOptions']:
                    colorObj = {}
                    for opt in itemMap['highLightOptions']:
                        colorObj[opt[0]] = opt[1]
                    # sliceStr=str(sliceStr)
                    if sliceStr in colorObj:
                        currentNode.setStyleSheet('color: {};'.format(colorObj[sliceStr]))
                        currentNode.setToolTip(' {}'.format(sliceStr))
                continue
            elif itemMap['dataSource'].startswith('RegArr'):
                if itemMap['showType'] in ['IP', 'DATETIME', 'CHARCODE']:
                    addrCount = int(itemMap['dataSource'].replace('RegArr',''))
                    # 先读取到原始值列表再处理
                    temValList = [ str(self.currentTabData[reg+idx]) if ((reg+idx) in self.currentTabData) else '' for idx in range(addrCount)]
                    if itemMap['showType'] == 'IP':
                        indexValueFormat = '{}.{}.{}.{}'.format(int(temValList[0])>>8, int(temValList[0])&0xff, int(temValList[1])>>8, int(temValList[1])&0xff)
                    elif itemMap['showType'] == 'DATETIME':
                        #格式化,[年,月日,时分,秒周],等数据
                        temValList = [ decimal2hex(nx) for nx in temValList]
                        intYear = temValList[0]
                        intMonth = temValList[1][0:2]
                        intDate = temValList[1][2:4]
                        intHour = temValList[2][0:2]
                        intMinute = temValList[2][2:4]
                        intSecond = temValList[3][0:2]
                        # intWeek = temValList[3][2:4]
                        indexValueFormat = '{}-{}-{}_{}:{}:{}'.format(intYear,intMonth,intDate,intHour,intMinute,intSecond)
                    elif itemMap['showType'] == 'CHARCODE':
                        # indexValueFormat = ''.join([chr(int(nx)) for nx in temValList if nx ])
                        indexValueFormat=''
                        for nx in temValList:
                            if nx:
                                leftByte=int(nx)>>8
                                rightByte=int(nx)&0xff
                                leftByte = '' if leftByte==0 else chr(leftByte)
                                rightByte = '' if rightByte==0 else chr(rightByte)
                                indexValueFormat += (leftByte + rightByte)
                    currentNode.setText(indexValueFormat)
                    currentNode.setToolTip(indexValueFormat) # 如需要QLineEdit控件显示前端字符，则需要之后设置光标位置为0
                    currentNode.setCursorPosition(0)
                    self.latestDataMap[idx] = str(indexValueFormat)
                    currentLoopArr[idx] = str(indexValueFormat)
                    continue
            elif itemMap['dataSource']=='Reg32':
                hVal = int(indexValue)
                lVal = int(self.currentTabData[reg+1]) if ((reg+1) in self.currentTabData) else 0
                indexValueFormat = hVal * 0x10000 + lVal
                currentNode.setText(str(indexValueFormat))
                currentNode.setToolTip('{} | {}'.format(hVal, lVal))
                self.latestDataMap[idx] = str(indexValueFormat)
                currentLoopArr[idx] = str(indexValueFormat)
                continue
            currentNode.setToolTip(' {}'.format(indexValue))
            if itemMap['showType'] == 'SELECT':
                # 如果不存在下拉选项就加入进去方便显示在界面上
                if indexValue not in optionMap:
                    currentNode.addItem(indexValue)
                    optionMap[indexValue] = indexValue
                value2label = optionMap[indexValue]
                currentNode.setToolTip(' {} | {}'.format(indexValue, value2label))
                currentNode.setCurrentText(value2label)
                self.latestDataMap[idx] = value2label
                currentLoopArr[idx] = value2label
                if itemMap['highLightOptions']:
                    colorObj = {}
                    for opt in itemMap['highLightOptions']:
                        colorObj[opt[0]] = opt[1]
                    if indexValue in colorObj:
                        currentNode.setStyleSheet('background: {};'.format(colorObj[indexValue]))
                    else:
                        currentNode.setStyleSheet('background: #fff;')
            elif itemMap['showType'] == 'SWITCHS':
                # 如果不存在下拉选项就加入进去方便显示在界面上
                if indexValue not in optionMap:
                    optionMap[indexValue] = indexValue
                else:
                    if (indexValue==itemMap['options'][0][0]) and (currentNode._switch_on is True): currentNode.toggleSwitch(False)
                    if (indexValue==itemMap['options'][1][0]) and (currentNode._switch_on is False): currentNode.toggleSwitch(True)
                    value2label = optionMap[indexValue]
                    currentNode.setToolTip(' {} | {}'.format(indexValue, value2label))
                    self.latestDataMap[idx] = value2label
                    currentLoopArr[idx] = value2label
            else:
                if itemMap['showType'] == 'SIGNED':
                    indexValue = str(int(indexValue)-65536) if int(indexValue)>32767 else indexValue
                _precision = itemMap['precision']
                if (_precision>0) and (indexValue not in optionMap):
                    indexValue = int(indexValue)/math.pow(10,_precision)
                    indexValue = format(indexValue, '.{}f'.format(_precision)) #设置保留N为小数，不足就补零
                if itemMap['showType'] == 'HEX':
                    indexValue = '{}H'.format(hex(int(indexValue))[2:].upper().zfill(4))
                elif itemMap['showType'] == 'HOURMINUTE':
                    intHour = str((decimal2hex(indexValue)[0:2])).zfill(2)
                    intMinute = str((decimal2hex(indexValue)[2:4])).zfill(2)
                    indexValue = '{}:{}'.format(intHour,intMinute)
                if itemMap['attr']=='RO':
                    # 如果文本框组件中存在下拉选项的配置就加入进去，显示值对应的文本在界面上
                    value2label = optionMap[indexValue] if (indexValue in optionMap) else str(indexValue)
                    # currentNode.setToolTip(' {} | {}'.format(indexValue, value2label))
                    currentNode.setText(value2label)
                    currentLoopArr[idx] = value2label
                else:
                    currentNode.setText(str(indexValue))
                    currentLoopArr[idx] = str(indexValue)
                self.latestDataMap[idx] = str(indexValue)
                if itemMap['highLightOptions']:
                    colorObj = {}
                    for opt in itemMap['highLightOptions']:
                        colorObj[opt[0]] = opt[1]
                    if indexValue in colorObj:
                        currentNode.setStyleSheet('background: {};'.format(colorObj[indexValue]))
                    else:
                        currentNode.setStyleSheet('background: #fff;')
                if itemMap['attr']=='RO':
                    currentNode.setStyleSheet('background: #eee;')
        filterArr = list(filter(None, currentLoopArr))
        if filterArr:
            self.saveAllLoopArrMap[self.readRegTitle].append([QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss_zzz')] + currentLoopArr )
            # 对比当前时间比上一次保存的时间差值，大于就自动保存
            currentTimeStamp = time.time()
            if (self.exportDateTimeLimit < currentTimeStamp):
                self.exportDateTimeLimit = currentTimeStamp + self.autoSaveInterval
                self.saveLoopDataFile()
        #第N圈开始的时候，去除只读N次的点位，重置全局的轮询点位
        if self.limitedReadTimes==self.globalReadTimes:
            if self.readOnceArr:
                self.readOnceArr = []
                self.setGroupAddrList(False)
        else: # 渲染所有的节点完成,计数加一
            if self.tabTitleList.index(self.readRegTitle)==0:self.limitedReadTimes+=1

    def setCurrentTabDisconnect(self):
        self.dock_content.append('===self.disconnectedTimer,disconnectedMapList_: {},==='.format(self.disconnectedMapList) )
        for regTitle in self.disconnectedMapList:
            if len(self.disconnectedMapList[regTitle])>1 and self.disconnectedMapList[regTitle][-1]==self.disconnectedMapList[regTitle][-2] and self.RxTxcountMap[regTitle]['connectResponse']:
                self.RxTxcountMap[regTitle]['connectResponse'] = False
                self.tw.setTabIcon(self.tabTitleList.index(regTitle), QIcon('./icons/disconnect.png'))
                self.disconnectedMapList[regTitle].append(self.RxTxcountMap[regTitle]['receiveCount'])
                self.disconnectedMapList[regTitle] = self.disconnectedMapList[regTitle][-2:]

    def updateReadTabData(self):
        for itemNode in self.rwNodeList:
            reg = int(itemNode.property('address'))
            indexValue = self.historyResData.get(reg,'')
            itemNode.setText(str(indexValue)) # 处理数据 # sliceLen=3+self.globalCurvesNum*2

    def updateWaveRenderData(self, rxFrameBuffer):
        self.heartBeat_count +=1
        try:
            rxFrameBuffer = self.historyBuffer + rxFrameBuffer
            while len(rxFrameBuffer) >=MIN_LEN:
                while (len(rxFrameBuffer)>=2 and not(rxFrameBuffer[0]==int(self.salveAddressNode.text()) and rxFrameBuffer[1]==0x16)):
                    rxFrameBuffer = rxFrameBuffer[1:]
                if len(rxFrameBuffer)>=MIN_LEN:
                    sliceLen = rxFrameBuffer[2]
                    # 切割每次接收的数据，然后根据固定的长度来做处理
                    sliceBit7 = format(sliceLen,'b').zfill(8)[0]
                    sliceLen = sliceLen&0x7f
                    if (len(rxFrameBuffer)>= (2+sliceLen)) and sliceLen>3:
                        sliceChunk = rxFrameBuffer[0: 2+sliceLen]
                        checksum = calc_byte_crc(sliceChunk[:-2])
                        if sliceChunk.endswith(checksum):
                            self.wave_rx_cnt+=1
                            self.wavelabel_rxt.setText("{}: {}".format(self.langData.get('channel_data_counts'),self.wave_rx_cnt))
                            if sliceBit7=='1':
                                self.statusBar.showMessage('---自动触发中---', 3000)
                            else:
                                splitChunk = sliceChunk[3: sliceLen]
                                if not splitChunk: return
                                vector_y = []
                                for i in range( 0, len(splitChunk), 2 ):
                                    rval = int.from_bytes(splitChunk[i:i+2], byteorder='big')
                                    if self.addrdataTypeList[int(i/2)]!='1':
                                        rval = rval-65536 if rval>32767 else rval
                                        vector_y.append(rval)
                                #当前的时间戳【精确到毫秒】把数据和时间戳添加到list，--为导出CSV做准备
                                currentDateStamp = round(time.time()*1000)
                                self.graph_y.append(vector_y )
                                self.save_graph_y.append([currentDateStamp] + vector_y )
                                # 缓存超过临界值就导出，分段处理，预防过大的文件
                                if len(self.save_graph_y) > self.max_export_len: self.exportSoftwaveDataCSV()
                                if self.toggle_plotGraphFlag:
                                    # 每次按照增加的时间增量再刷新图像
                                    if (self.historyTime + 30) < currentDateStamp: self.historyTime = currentDateStamp
                                    # if len(self.graph_y)>50000: self.graph_y = self.graph_y[-20000:]
                                    self.rawSlicedData = self.graph_y[-1 * int(self.cacheLengthNode.text()):]
                                    self.refresh_softWavePlot()
                        rxFrameBuffer=rxFrameBuffer[2+sliceLen:]
                    else:
                        rxFrameBuffer=rxFrameBuffer[2:]
                else: rxFrameBuffer=rxFrameBuffer[2:]
            else: self.historyBuffer = rxFrameBuffer
        except Exception as e:
            logger.error('--- update_render_data_ERR: {}! ---'.format(e))
    def heartBeatCheck(self):
        if self.heartBeat_count in self.heartBeat_countList:
            self.dataisUpdating = False
            self.historyBuffer = b''
            self.waveprogressbar.setValue(0)
            self.heartBeat_Timer.stop()
        else:
            self.heartBeat_countList.append(self.heartBeat_count)
            self.heartBeat_countList = self.heartBeat_countList[-2:]
            # 心跳检测正常就重置相关的参数和状态量
            self.dataisUpdating = True
            self.waveprogressbar.setValue(1)
    def exportSoftwaveDataCSV(self):
        if not self.save_graph_y:
            return self.checkCreateDateDir()
        currentTime = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm')
        fileName = 'softWaveData_{}.csv'.format(currentTime)
        try:
            with open( 'exportlog/{}/{}'.format(self.currentDate, fileName), 'a+', encoding='utf_8_sig', newline='') as f:
                f_csv = csv.writer(f)
            titles = ['timestamp'] + [item['name'] for item in self.selectedChannelMap]
            f_csv.writerow( titles)
            # 头部信息
            f_csv.writerows(self.save_graph_y)
            self.save_graph_y = []
            self.statusBar.showMessage('---export data to {} success---'.format(fileName), 3000)
        except Exception as e:
            logger.error('--- save export_csv_ ERR: {}! ---'.format(e))
            self.statusBar.showMessage('--- save export_csv_ERR: {}! ---'.format(e), 3000)
    def exportMonitorDataCSV(self):
        if not self.monitor_graph_y:
            return self.checkCreateDateDir()
        currentTime = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm')
        fileName = 'realTimeData_{}.csv'.format(currentTime)
        try:
            with open( 'exportlog/{}/{}'.format(self.currentDate, fileName), 'a+', encoding='utf_8_sig', newline='') as f:
                f_csv = csv.writer(f)
            titles = ['timestamp'] + [item['name'] for item in self.selectedChannelMap]
            f_csv.writerow( titles)
            # 头部信息
            f_csv.writerows(self.monitor_graph_y)
            self.monitor_graph_y = []
            self.plot_rx_cnt = 0
            self.statusBar.showMessage('---export data to {} success---'.format(fileName), 3000)
        except Exception as e:
            logger.error('--- save export_csv_ ERR: {}! ---'.format(e))
            self.statusBar.showMessage('--- save export_csv_ERR: {}! ---'.format(e), 3000)
    def saveLoopDataFile(self):
        if not self.saveLoopDataChk.isChecked():
            for keyName in self.saveAllLoopArrMap:
                self.saveAllLoopArrMap[keyName]=[]
            return
            # 先判断有数据，再进一步保存数据
        notSaveFlag = True
        for k,v in self.saveAllLoopArrMap.items():
            if v:
                notSaveFlag = False
                break
            if notSaveFlag:
                return self.checkCreateDateDir()
            for idx,keyName in enumerate(self.saveAllLoopArrMap):
                saveDataArr = self.saveAllLoopArrMap[keyName]
                if not saveDataArr:
                    continue
                fName = self.fileNameList[idx]
                # 如果检测当前的文件不存在，就添加标题头那一行,并且命名为最新的时间节点名称
                if not os.path.exists('exportlog/{}/{}'.format(self.currentDate, fName)):
                    saveDataArr.insert(0,['timestamp']+ self.regItemNameMap[keyName])
                    fName = '{}_{}.csv'.format(QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss'), self.tabTitleList[idx])
                    self.fileNameList[idx] = fName
                else:
                    fsize = os.path.getsize('exportlog/{}/{}'.format(self.currentDate, fName))
                    # 返回的是字节大小
                    if (fsize/1024/1024)>self.maxfileSize:
                        #超过30M的文件，判断太大，就需要重新命名保存新文件了
                        fName = '{}_{}.csv'.format(QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss'), self.tabTitleList[idx])
                        self.fileNameList[idx] = fName
                        #每次重命名就设置为最新的文件名
                        saveDataArr.insert(0,['timestamp']+ self.regItemNameMap[keyName])
                        try:
                            with open('exportlog/{}/{}'.format(self.currentDate, fName), 'a+', encoding='utf_8_sig', newline='') as f:
                                f_csv = csv.writer(f)
                                f_csv.writerows(saveDataArr)
                            self.saveAllLoopArrMap[keyName]=[]
                        except Exception as e:
                            logger.error('--- save export_csv_ ERR: {}! ---'.format(e))
                            fileReName = '{}_{}.csv'.format(QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss'), self.tabTitleList[idx])
                            self.fileNameList[idx] = fileReName
                            #每次重命名就设置为最新的文件名
                            saveDataArr.insert(0,['timestamp']+ self.regItemNameMap[keyName] )
                            with open('exportlog/{}/{}'.format(self.currentDate,fileReName), 'a+', encoding='utf_8_sig', newline='') as f:
                                f_csv = csv.writer(f)
                                f_csv.writerows(saveDataArr)
                            self.saveAllLoopArrMap[keyName]=[]
                            # 导出一次csv以后，把缓存的数据清零处理【重要！】
                            # 导出写入的点位的值-
                            if len(self.writeDataArr)==0:
                                return
                            wFileName = 'write_vals_{}.csv'.format(QDateTime.currentDateTime().toString('yyyy-MM-dd'))
                            appendHeader=''
                            if not os.path.exists('exportlog/{}/{}'.format(self.currentDate,wFileName)):
                                appendHeader = ['timestamp', 'writeRegName','writeRegAddr', 'writeRegVal']
                                try:
                                    with open('exportlog/{}/{}'.format(self.currentDate,wFileName), 'a+', encoding='utf_8_sig', newline='') as fw:
                                        f_csv = csv.writer(fw)
                                    if appendHeader:
                                        f_csv.writerow(appendHeader)
                                        f_csv.writerows(self.writeDataArr)
                                        self.writeDataArr =[]
                                except Exception as e:
                                    logger.error('--- save write_csv_ ERR: {}! ---'.format(e))
                                    with open('exportlog/{}/{}'.format(self.currentDate, 'write_vals_{}.csv'.format(QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss'))), 'a+', encoding='utf_8_sig', newline='') as fw:
                                        f_csv = csv.writer(fw)
                                        f_csv.writerow(['timestamp', 'writeRegName','writeRegAddr', 'writeRegVal'])
                                        f_csv.writerows(self.writeDataArr)
                                    self.writeDataArr =[]
    def resetTabStatus(self):
        for (index, tabContent) in enumerate(self.editableTabs):
            tabName = tabContent['title']
            self.tw.setTabIcon(index, QIcon('./icons/disconnect.png'))
            self.RxTxcountMap[tabName]['connectResponse'] = False
            self.RxTxcountMap[tabName]['sendCount'] = 0
            self.RxTxcountMap[tabName]['receiveCount'] = 0
            self.RxTxcountMap[tabName]['readErrCount'] = 0
            self.RxTxNodeMap[tabName][0].setText('{}: 0'.format(self.langData.get('send_count')))
            self.RxTxNodeMap[tabName][1].setText('{}: 0'.format(self.langData.get('receive_count')))
    def loopOneRead(self):
        # 设置间隔200ms检测是否有收到回应，否则继续发送
        if self.serialCom.isOpen():
            self.send_time.start(self.loopWaitTime)
            # 设置定时器的定时间隔时间，为[N]ms，
            if not self.groupAddrList or self.listenerChk.isChecked():
                self.send_time.stop()
                # '已停止所有的轮询'
                self.globalStatus.setText(self.langData.get('all_loop_stoped'))
                return
            addrGroup = self.groupAddrList[self.loopIdx % len(self.groupAddrList)]
            self.readRegAddr = int(addrGroup['addr'])
            self.readRegCount = int(addrGroup['count'])
            self.edgeNumber = 5 + int(addrGroup['count']) *2
            self.readRegTitle = addrGroup['title']
            loopBuffer = getreadcrc(addrGroup['connect485Id'], addrGroup['addr'], addrGroup['count'])
            self.Com_Send_Data(loopBuffer)

    def reloopOneRead(self):
        self.dock_content.append('===reloopOneRead, idx_: {}==='.format(self.timerIdx))
        if self.loopReadFlag and (self.timerIdx > 5):
            # 读值超过一定次数无响应就抛出错误提示,并重置轮询的方法重新开始
            CustomToast('轮询无回复,请检查!')
            self.loopReadIndex = 0
            self.loopReadFlag = False
            self.insertReadFlag = False
            self.receiveReadFlag = False
            self.setGroupAddrList(False)
        if self.serialCom.isOpen():
            if self.timerIdx > (self.maxResponseIdx+10):
                # CustomToast('轮询无回复,请检查连接!')
                # self.globalStatus.setText('轮询无回复,请检查连接!')
                self.send_time.stop()
                self.timerIdx = 0
                # 轮询无回复就会继续发送不要停止
                self.loopIdx = 0
                self.historyData = b''
                self.loopOneRead()
            else:
                self.timerIdx +=1
                self.loopIdx+=1
                #读点无响应就继续下一个超过次数判定为当前的tab页断链
                if self.readRegTitle:
                    self.RxTxcountMap[self.readRegTitle]['readErrCount']+=1
                    if self.readRegTitle and (self.RxTxcountMap[self.readRegTitle]['everyLoopCount'] <= self.RxTxcountMap[self.readRegTitle]['readErrCount']):
                        self.statusBar.showMessage('{}, 轮询无回复,请检查!'.format(self.readRegTitle), 3000)
                        self.RxTxcountMap[self.readRegTitle]['readErrCount']=0
                        self.RxTxcountMap[self.readRegTitle]['connectResponse'] = False
                        self.tw.setTabIcon(self.tabTitleList.index(self.readRegTitle), QIcon('./icons/disconnect.png'))
                        self.setGroupAddrList(False)
                        self.timerIdx=0
                        #某个tab页断开后给出提示条，并重置开始下一个计数周期
                        # 关闭再打开串口看是否成功,来判断是否连接的串口存在
                        connectResponseCount = len(self.tabAutoLoopList)
                        if self.tabAutoLoopList and (self.readRegTitle==self.tabAutoLoopList[-1]):
                            for tab_name in self.tabAutoLoopList:
                                if self.RxTxcountMap[tab_name]['connectResponse']==False:
                                    connectResponseCount-=1
                            if connectResponseCount == 0:
                                self.send_time.stop()
                                self.serialCom.close()
                                self.serialPortList.setEnabled(True)
                                self.baudRateList.setEnabled(True)
                                self.globalStatus.setText(self.langData.get('port_closed'))
                                self.key_text_toggle.setText(self.langData.get('open_port'))
                                self.dock_content.append('=============self.serialCom.close=============')
                                portList = [info.portName() for info in QSerialPortInfo.availablePorts()]
                                if self.currentComName not in portList:
                                    # return
                                    #轮询一个周期没回复就断开连接停止定时器
                                    self.dock_content.append('=== 未检测到串口,请检查!===')
                                    if self.toggle_text.isChecked():
                                        self.rightList.appendToBottom('=== {} 未检测到串口,请检查! ==='.format( getCurrentStamp()))
                                    self.Com_Toggle_Button_clicked('autoToggle')
                                else:
                                    self.dock_content.append('=== 轮询无回复,请检查!===')
                                    if self.toggle_text.isChecked():
                                        self.rightList.appendToBottom('=== {} 轮询无回复,请检查! ==='.format( getCurrentStamp()))
                                    self.Com_Toggle_Button_clicked('autoToggle')
                self.historyData = b''
                self.loopOneRead()
    def showMessage(self, content='提示消息', duration=3000):
        self.msg_box_hint = QMessageBox()
        self.msg_box_hint.setIcon(QMessageBox.Information)
        self.msg_box_hint.setWindowTitle(self.langData.get('warning_msg'))
        self.msg_box_hint.setText(content)
        self.msg_box_hint.show()
        self.delayTimer.singleShot(duration,lambda: self.msg_box_hint.close())
    def initGlobalParams(self):
        # 初始化之前先定义控制台的组件，所有的打印信息都放这里
        self.dock_widget=None
        self.dock_content = QTextEditWithButtons()
        # 定义几个延时执行的定时器，方便调用
        self.delayTimer = QTimer(self)
        self.execDelayTimer = QTimer(self)
        self.disconnectedMapList = {}
        self.disconnectedTimer = QTimer(self)
        # self.disconnectedTimer.setSingleShot(True)
        # 设置定时器是否为单次触发。
        self.disconnectedTimer.timeout.connect(self.setCurrentTabDisconnect)
        self.intervalTimer = QTimer(self)
        self.intervalTimer.timeout.connect(self.sendBufferText)
        self.responseTimer = QTimer(self)
        self.responseTimer.timeout.connect(self.throwErrHandler)
        self.delayUpdatePosFlag = True
        self.delayUpdatePosTimer = QTimer(self)
        self.delayUpdatePosTimer.timeout.connect(self.getViewRange)
        #用来存储心跳记录【定时检测软件示波器有无信号接收】的列表，比较上一次是否相同
        self.heartBeat_count=0
        self.heartBeat_countList = []
        self.heartBeat_Timer = QTimer(self)
        self.heartBeat_Timer.timeout.connect(self.heartBeatCheck)
        # 创建一个QTimer对象---# 给QTimer设定一个时间，每到达这个时间一次就会调用一次该方法
        self.send_time = QTimer(self)
        self.send_time.timeout.connect(self.reloopOneRead)
        # oTA响应失败的提示
        self.otaResponseTimer = QTimer(self)
        self.otaResponseTimer.timeout.connect(self.throwOTAerr)
        self.logResponseTimer = QTimer(self)
        self.logResponseTimer.timeout.connect(self.throwLOGerr)
        self.langType = 'zh'
        self.winType = 'Fusion'
        self.latestLangType = 'zh'
        #上一次切换时候的多语言的类型，记录方便进行对比
        self.configSettingMap = {}
        #存储缓存文件信息
        self.langData = {}
        self.readBuffer = ''
        self.saveBufferList = []
        #存储后台保存的报文信息
        self.limitedReadTimes = 0
        #读点周期的计数【N圈轮询】有限的读点次数
        self.node_count=0
        #界面上动态添加的节点计数
        self.readRegAddr = 0
        self.readRegCount = 0
        self.timerIdx = 0
        self.writeDataArr = []
        #保存写入的数据
        self.latestDataMap = []
        #用来存储【上一次】最近一次的输入框里面的文本，用于对比
        self.dataChangedFlag = False
        #是否发生数据被改变了
        self.loopIdx = 0
        #用来统计每一圈的轮询计数器
        # 接收和发送的计数
        self.sendIdx = 0
        self.receiveIdx = 0
        self.edgeNumber = 8
        #用来判断收发报文长度是否一致的flag
        #用来存放每次接受的数据，可能会多次接受才能组成一个完整的数据片段
        self.historyData = b''
        self.writeOnlyList = []
        #存放只读的点位数据
        self.readOnceList = []
        #存放只读一次的点位对象数据
        self.readOnceArr = []
        #存放只读N次的点位列表
        self.readOnceArrCopy = []
        self.readTimesMap = {}
        #存放只读N次的点位和次数的map信息
        self.readTimesMapCopy = {}
        self.currentDate = ''
        #存放数据的当前文件夹
        self.regNameList = []
        self.regAddrList = []
        #存放所有的【点位】数据
        self.groupAddrList = []
        #存放【点位，个数】list数据
        self.loopBufferList = []
        #存放【buffer】list数据
        self.historyBuffer = b''
        self.historyResData = {}
        self.signedAddrList = []
        #用来存放有符号的地址列表
        self.showtypeListMap = {}
        self.currentTabData = {}
        #当前某一刻tab存放的读点的返回值
        self.historyResDataMap = {}
        #根据tab页的标题来区分存放的读点的返回值
        self.rawBinaryMap = {}
        #存放点位的二进制bit位的数据
        #存放所有的【点位】数据
        self.readRegTitle = ''
        self.regItemMapArr = []
        self.regItemNameMap = {}
        self.regItemNodeMap = {}
        self.saveAllLoopArrMap = {}
        self.regItemNodeList = []
        self.allItemNodeList = []
        self.startAllTabFlag = True
        self.stopAllTabFlag = False
        self.maxResponseIdx = 0
        #存放tab页里轮询计数的最大值
        self.tabTitleList = []
        #存放所有tab的标题
        self.fileNameList = []
        self.RxTxcountMap = {}
        #存放所有tab内部的收发计数的容器
        self.RxTxNodeMap = {}
        #存储收发节点的对象
        self.langNodeMap = {}
        self.editableListMap = {}
        self.editableTabs = []
        #存放【tab标题:站号，地址等信息】列表
        self.nameAddressMap = {}
        #存放【点位-地址】键值对
        # 写入的地址和值
        self.loopReadFlag = False
        self.loopWriteFlag = False
        #连续不间断写入值的标记
        self.loopWriteBatchFlag = False
        self.loopReadIndex = 0
        self.loopWriteIndex = 0
        self.insertWriteFlag = False
        # 插入写值的指令的标签
        self.receiveWriteFlag = False
        self.insertReadFlag = False
        # 插入读值的指令的标签
        self.insertReadMCUFlag = False
        #加入读MCU值的标签
        self.mcuAddrValueList = []
        #加入读MCU值的地址值和数据值的列表
        self.mcuDataValueList = []
        self.receiveReadFlag = False
        self.writeRegName = ''
        self.writeRegAddr = 0
        self.writeRegVal = 0
        self.writeBuffer = []
        self.stationAddress = 1
        self.columnNum = 3
        self.maxfileSize = 10
        self.sleepTime = 0.003
        #每次响应以后的间隔时间[s]，
        # 超时指令和指令间隔时间
        self.updateStampWaitTime = 10
        #每次更新最新的时间戳的间隔时间[ms]，
        self.loopWaitTime = 100
        #每次轮询间隔时间[ms]，
        self.writeWaitTime = 150
        #写入等待响应的时间，超时默认写失败
        self.pollingSize = 22
        self.bufferTextLen = 500
        self.historyDataMaxLen = 10000
        #报文数据长度超出就清空【判断为异常情况】
        self.readBytesOnlyFlag=False
        self.mergeContinuousFlag = False
        #是否跳过断点，忽略断点归并连续读点
        self.exportDateTimeLimit = time.time()
        self.autoSaveInterval = 120
        self.exportMaxCount = 10000
        self.selectOptionsMap = {}
        #存储select_map_options【下拉选ID对应的选项详细信息】
        self.regItemList = []
        #存储读取的pwf/csv文件的键值对的数据
        self.regAddrLineMap = {}
        self.currentComName = ''
        self.existComPortFlag =False
        self.msg_box_hint = None
        self.channelListMap = {}
        self.channelAddrList = []
        self.plotMonitorGraphFlag = False
        self.plotGraphFlag = False
        self.plotGraphType = None
        self.max_len_x = 200
        self.graph_y = []
        #用来存储波形的数据
        self.monitor_graph_y = []
        self.selectedChannelMap = []
        #存储选中的通道的点位名称偏移量等信息
        self.checkedAddrList = []
        self.checkedAddrMap = {}
        self.channelNodeList = []
        # 0516读取配置列表新增的偏移和放大系数等字段
        self.plotWidDialogIsVisited=False
        #记录弹框是否被打开过
        self.regNameInfoList = []
        self.checkedChannelList = []
        self.regWidthList = [1]*20
        self.regScaleList = [1]*20
        self.regOffsetList = [0]*20
        self.regColorList = ['#FFD700','#00FF7F','#BDB76B','#FF0000','#CD5C5C','#FFA07A','#FF8C00','#B8860B','#EEE8AA','#808000','#9ACD32', '#6B8E23','#2E8B57','#EEE8AA','#D2691E','#00FFFF','#E0FFFF','#4682B4','#191970','#4169E1','#8A2BE2','#D8BFD8','#FF1493', '#FAEBD7','#8B4513', '#F4A460','#708090','#FFAA00']
        self.delayUpdateNode=None
        self.rwNodeList = []
        self.labelNodeList = []
        self.tracerList = []
        #添加游标的列表存储N条游标的信息
        self.tracerLabelList = []
        self.checkNodeList = []
        self.rawByteList = []
        #bin文件原始数据
        self.logdataMapList = []
        # 生成文件唯一标识符，用来判断是本地或者外来的
        self.fileUniqueCode = round(987654321).to_bytes(4, byteorder='big')
        self.prependFileHeader = b''
        self.fileRawDataContent = b''
        self.stopFilePackageFlag = False
        self.logDialogOpened = False
        self.logTXBuffer = b''
        self.otaDialogOpened = False
        self.currentType = 'getdevInfo'
        self.otaCurrentCount = 3
        self.file_checksum = ''
        self.otaTXBuffer = ''
        #ota模式下发送的报文记录
        self.header4Byte = ''
        self.updateIndex = 0
        #升级索引[第几个包]
        self.totalUpdateCount = 0
        #升级总次数
        self.latestSearchTextList = []
        #历史查找文本的[文本检索和文本标记]
        self.latestSearchTextMap = {}
        self.colorList = ['pink', 'Crimson', 'DeepPink', 'Purple', 'MediumPurple', 'Blue', 'RoyalBlue', 'DoderBlue', 'SkyBlue', 'Cyan', 'Teal', 'SpringGreen', 'Lime', 'Green', 'LightYellow', 'Yellow', 'Gold', 'Wheat', 'Orange', 'Chocolate', 'Tomato', 'Red', 'LightGrey', 'Gray', 'Olive']
        self.globalReadTimes=1
        #重复读的次数，为简单处理，只取其中最大值
        self.currentTab = {}
        self.duplicatedIdList = []
        self._refresh_cnt = 5
        #刷新时间默认位N个点，如果采样周期大（速度慢）就改为5个点刷新一次
        self.plot_rx_cnt = 0
        #实时数据的画图更新的计数
        self.toggleChannelGridFlag = None
        #设置通道的弹框区分是全部节点还是读数据选通道的模式
        self.checkedNameList = []
        self.xlsxDataList = []
        self.openeddataNameList = []
        self.latestTabIndex = -1
        #存储当前tab页的索引
        self.alternateReadWriteFlag = False
        #交替读写的标记和索引
        self.alternateIndex = 0
        self.globlaBoxNodeMap = {}
        # 全局的曲线条数，初始配置项后即获取到
        self.globalCurvesNum = 8
        self.triggerSource='00000000'
        self.settingModeStr='00000000'
        self.latestRowIdx = 0
        self.uuidBinaryMap = {}
        self.addrdataTypeList = []
        self.channelAddrRawMap = {}
        self.channelAddrInfoMap = {}
        self.channelAddrInfoList = []
        self.save_graph_y = []
        #用来保存数据的列表缓存
        self.max_export_len = 50000
        # 导出临界值, 超过这个开始自动保存数据
        #用于记录存储当前时间，便于比较刷新界面图形
        self.historyTime = round(time.time()*1000)
        self.wave_rx_cnt=0
        self.mark_rx_cnt=0
        self.sendTxData=''
        #打开或关闭的发送的报文
        self.curveList = []
        self.monitorCurveList = []
        self.latestTimeStamp = round(time.time()*1000)
        self.toggle_plotGraphFlag = False
        self.rawSlicedData = []
        self.timeSlicedData = []
        #存储实时数据的时间记录的列表
        # 软件示波器相关的参数
        self.dataisUpdating = False
        #数据是否正在更新【示波器是否在打开的状态还是停止更新了？】
        self.rangeStartBorder=0
        self.rangeEndBorder=0
        #每次更新图形记录最新的右边边界，作为截取数据的标的
        self.tempXrange = [0,0]
        self.sorted_graph_y = []
        #倒序添加数据,按照最新的时间放在头部的数据
        self.fixedLine_xa = None
        self.fixedLine_xb = None
        self.proxy = None
        self.cursorLine = None
        self.showLabel = None
        self.readHistoryFlag = False
        self.input_XA =0
        self.input_XB =0
        self._isDataEnabledOpen = False
        #监控打开或关闭的使能
        self.nameColorMap = {}
        self.listenerState=''
        self.proxy2 = None
        self.cursorLine2 = None
        self.showLabel2 = None
        self.customPlotGraph = None
        self.toggle_plotGraphFlag2 = False
        self.crawBuffer = ''
        #记录当前点击的行原始数据【文件名，开始和结束时间等信息】
        self.recordfileName = ''
        self.parserRawstr = ''
        #记录文件的解析之前的内容
        self.parserRawstrList = []
        self.parserRawstrListCopy = []
        self.parserfileList = []
        #记录文件-解析文件的映射表【解析对象的列表】
        self.parserTitleMap = {}
        #解析文件的映射表
        self.parserRawstrLen = 0
        self.accSlicedLen = 0
        #添加一个累计解析的字节的长度，用于记录对比
        self.currentFileLogType = ''
        #文件上传过程的标签flag用于对比识别当前为文件上传的哪一个过程
        self.searchResults = []
        self.currentResultIndex = -1
        self.currentSearchText = ''
        # 获取配置文件信息
    def loadConfigFile(self):
        if not os.path.exists('./config/downloadCFG'):
            self.dock_content.append('create_downloadCFG_directory!')
            os.makedirs('./config/downloadCFG')
            if not os.path.exists('./exportlog/uploadfile'):
                self.dock_content.append('create_uploadfile_directory!')
                os.makedirs('./exportlog/uploadfile')
                if not os.path.exists('./exportlog/outputfile'):
                    self.dock_content.append('create_outputfile_directory!')
                    os.makedirs('./exportlog/outputfile')
                    configMap = {}
                    cfgFilePath = './config/connectionConfig.txt'
                    if not os.path.exists(cfgFilePath):
                        return QMessageBox.critical(self, 'critical_err', 'missing_file: {}, please_check!'.format(cfgFilePath))
                    try:
                        with open (cfgFilePath, 'r', encoding='utf8') as f:
                            cfgLines = f.readlines()
                            for i in cfgLines:
                                item = re.split(r"[ ]+", i.replace('\n','') )
                                if len(item)==2:
                                    configMap[item[0]] = item[1]
                                else:
                                    self.dock_content.append('---errCfgitem : {}---'.format(item))
                                    self.sleepTime = int(configMap['sleepTime'])/1000 if 'sleepTime' in configMap else 0.001
                                    self.columnNum = int(configMap['columnNum'])*3 if 'columnNum' in configMap else 4
                                    self.pollingSize = int(configMap['pollingSize']) if 'pollingSize' in configMap else 22
                                    self.bufferTextLen = int(configMap['bufferTextLen']) if 'bufferTextLen' in configMap else 500
                                    self.exportMaxCount = int(configMap['exportMaxCount']) if 'exportMaxCount' in configMap else 10000
                                    self.autoSaveInterval = int(configMap['autoSaveInterval']) if 'autoSaveInterval' in configMap else 120
                                    self.writeWaitTime = int(configMap['writeWaitTime']) if 'writeWaitTime' in configMap else 150
                                    self.loopWaitTime = int(configMap['loopWaitTime']) if 'loopWaitTime' in configMap else 100
                                    self.updateStampWaitTime = int(configMap.get('updateStampWaitTime', 10))
                                    self._refresh_cnt = int(configMap['refreshCount']) if 'refreshCount' in configMap else 10
                                    self.maxfileSize = int(configMap['maxfileSize']) if 'maxfileSize' in configMap else 30
                                    self.mergeContinuousFlag = True if 'mergeContinuousFlag' in configMap else False
                                    self.historyDataMaxLen = int(configMap.get('historyDataLen', 10000))
                                    self.readBytesOnlyFlag = True if 'readBytesOnlyFlag' in configMap else False
                    except Exception as e:
                        logger.error('---open_cfg_err: {}!---'.format(e))
                        QMessageBox.critical(self, 'critical_err', '---open_cfg_err: {}!---'.format(e))
                        # 加载缓存文件信息
                        if not os.path.exists('./config'):
                            return QMessageBox.critical(self, 'critical_err','--- missing [./config] folder, please check! ---' )
                            #检测到没有历史数据的文件夹就弹框使用说明【用来区分是否头一次使用这个软件】
                            # self.execDelayTimer.singleShot(3000, self.onHelpAbout)
                        if not os.path.exists('./config/localSettings.txt'):
                            return self.writeLocalSettings()
                        try:
                            with open ('./config/localSettings.txt', 'r', encoding='utf8') as f:
                                localLines = f.readlines()
                            self.configSettingMap = {}
                            for i in localLines:
                                item = re.split(r"[ ]+", i.replace('\n','') )
                            if len(item)==2:
                                self.configSettingMap[item[0]] = item[1]
                            else:
                                self.dock_content.append('---errSettingsitem : {}---'.format(item))
                                self.langType = self.configSettingMap.get('langType', 'zh')
                                self.winType = self.configSettingMap.get('winType', 'Fusion')
                                self.globalCurvesNum = int(self.configSettingMap.get('globalCurvesNum', 8))
                                self.latestLangType = self.langType
                                self.resize(int(self.configSettingMap.get('winWidth',1100)), int(self.configSettingMap.get('winHeight', 700)))
                                app.setFont(QFont(self.configSettingMap.get('fontFamily', "Microsoft YaHei"), int(self.configSettingMap.get('fontSize',12))))
                        except Exception as e:
                            logger.error('---err: read local_setting_file Err!---', e)
                            QMessageBox.critical(self, 'critical_err', '---open_localSetting_err: {}!---'.format(e))
    def writeLocalSettings(self):
        self.configSettingMap['receiveHexFlag'] = self.receiveHexNode.isChecked()
        self.configSettingMap['screenWidthTime'] = self.screenWidthNode.text()
        self.configSettingMap['ioSlaveAddr'] = self.stationNum.text()
        self.configSettingMap['rwSlaveAddr'] = self.rwStationNode.text()
        self.configSettingMap['rwStartAddr'] = self.startAddrNode.text()
        self.configSettingMap['otaSlaveAddr'] = self.devInputNode.text()
        self.configSettingMap['logSlaveAddr'] = self.devInputNode.text()
        # self.configSettingMap['logDevId'] = self.devInputNode.text()
        self.configSettingMap['modeSlaveAddr'] = self.salveAddressNode.text()
        self.configSettingMap['modeSamplePeriod'] = self.samplePeriodNode.text()
        self.configSettingMap['modeSampleIndex'] = self.sampleCountNode.text()
        self.configSettingMap['cacheLength'] = self.cacheLengthNode.text()
        self.configSettingMap['waveModetype'] = self.modeTypeList.currentIndex()
        self.configSettingMap['waveDatatype'] = self.dataTypeList.currentIndex()
        self.configSettingMap['waveTriggertype'] = self.triggerTypeList.currentIndex()
        try:
            with open('./config/localSettings.txt', 'w', encoding='utf8') as f:
                for key,val in self.configSettingMap.items():
                    f.write('{} {}\n'.format(key, val))
        except Exception as e:
            logger.error('---err: write_local_setting_file Err!---', e)
            # 处理窗口调整大小事件
    def resizeEvent(self, event):
        # 获取窗口大小
        window_size = self.size()
        self.configSettingMap['winWidth'] = str(window_size.width())
        self.configSettingMap['winHeight'] = str(window_size.height())
        #保存后台报文数据
    def saveBufferListItem(self):
        if len(self.saveBufferList)==0:
            return self.checkCreateDateDir()
        currentTime = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh')
        fileName = 'export_text_{}.txt'.format(currentTime)
        with open('exportlog/{}/{}'.format(self.currentDate,fileName), 'a', encoding='utf8') as f:
            f.write( '\n'.join(self.saveBufferList))
            f.write( '\n' )
            #最后一行添加换行
        self.saveBufferList=[]
    def checkCreateDateDir(self):
        if not self.currentDate or not os.path.exists('./exportlog/{}'.format(self.currentDate)):
            self.currentDate = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss')
            os.makedirs('./exportlog/{}'.format(self.currentDate))
            #保存弹框列表中的报文数据
    def saveListItem(self):
        if self.rightList.toPlainText()=='':
            return self.checkCreateDateDir()
        currentTime = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss')
        fileName = 'export_text_{}.txt'.format(currentTime)
        with open('exportlog/{}/{}'.format(self.currentDate,fileName), 'a', encoding='utf8') as f:
            f.write(self.rightList.toPlainText())
        self.statusBar.showMessage('---export data to {} success---'.format(fileName), 3000)
        # 清空删除全部报文【包括计数】
    def DeleteListItem(self):
        self.rightList.clear()
        self.sendIdx=0
        self.label_txt.setText(str(self.sendIdx))
        self.receiveIdx=0
        self.label_rxt.setText(str(self.receiveIdx))
    def openCSVfile(self):
        openfile_name = QFileDialog.getOpenFileName(self,'打开csv','','csv file( *.csv)')
        try:
            with open (openfile_name[0], 'r', encoding='utf_8_sig', errors='ignore') as f:
                csvLines = f.readlines()
                self.regItemList = [i.replace('\n','').split(',') for i in csvLines]
            self.renderIOtablelist()
        except Exception as e:
            logger.error('--- read csv_file ERR: {}! ---'.format(e))
    def openPWFfile(self):
        openfile_name = QFileDialog.getOpenFileName(self,'打开pwf','','pwf file( *.pwf)')
        try:
            with open (openfile_name[0], 'rb' ) as f:
                rawContent = f.read()
                rawString = binascii.b2a_hex(rawContent).decode('ascii')
                rawList = re.findall('(.{4})', rawString)
            self.regItemList = []
            if len(rawList)%2!=0:
                self.dock_content.append('pwf文件内容错误【长度有误】!')
                rawList.pop()
                for i in range( 0, len(rawList), 2 ):
                    self.regItemList.append([int(rawList[i], 16) , int(rawList[i+1], 16) ])
                self.renderIOtablelist()
        except Exception as e:
            logger.error('--- read pwf_file ERR: {}! ---'.format(e))
    def open_ioDialog(self):
        if int(self.passwordLabel.text())<3:
            return CustomToast('密码等级权限不够,请检查!')
        ioDialog.show()
        ioDialog.move(self.geometry().left(), self.geometry().top())
        # 设置对话框的位置
        ioDialog.raise_()
    def renderIOtablelist(self):
        try:
            self.regAddrLineMap = {}
            ioTableList.setRowCount(len(self.regItemList))
            for (row,regItem) in enumerate(self.regItemList):
                self.regAddrLineMap[int(regItem[0])]=row
                wAddrItem = QTableWidgetItem(str(regItem[0]))
                wValItem = QTableWidgetItem(str(regItem[1]))
            rawValItem = QTableWidgetItem('')
            wStateItem = QTableWidgetItem('x')
            wAddrItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            wValItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            rawValItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            wStateItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            # 设置文本居中
            wAddrItem.setTextAlignment(Qt.AlignHCenter)
            wValItem.setTextAlignment(Qt.AlignHCenter)
            rawValItem.setTextAlignment(Qt.AlignHCenter)
            wStateItem.setTextAlignment(Qt.AlignHCenter)
            ioTableList.setItem(row, 0, wAddrItem)
            ioTableList.setItem(row, 1, wValItem)
            ioTableList.setItem(row, 2, rawValItem)
            ioTableList.setItem(row, 3, wStateItem)
            # ioDialog.show()
            if not self.regItemList:
                ioDialog.setEnabled(False)
                addrList = sorted(list(self.regAddrLineMap.keys()))
                if(addrList[-1] - addrList[0] +1) > len(addrList):
                    multiWriteListBtn.setEnabled(False)
                else:
                    multiWriteListBtn.setEnabled(True)
        except Exception as e:
            logger.error('--- render_tablelist ERR: {}! ---'.format(e))
    def readRawValue(self):
        self.timerIdx = 0
        self.send_time.stop()
        self.delayTimer.singleShot(100, self.loopReadList )
    def loopReadList(self):
        self.groupAddrList = []
        for regItem in self.regItemList:
            self.groupAddrList.append({ 'addr': int(regItem[0]), 'count': 1, 'title': '', 'connect485Id': int(self.stationNum.text().strip()), })
        self.readDataMap = {}
        self.loopReadFlag = True
        self.historyData = b''
        self.loopOneRead()
    def saveCSVfile(self):
        try:
            openfile_name = QFileDialog.getSaveFileName(self,'保存csv','','csv files( *.csv)')
            with open(openfile_name[0], 'w', encoding='utf_8_sig', newline='') as f:
                f_csv = csv.writer(f)
            for row_line in range(ioTableList.rowCount()):
                f_csv.writerow([ioTableList.item(row_line, 0).text(), ioTableList.item(row_line, 2).text()])
                # f_csv.writerows( self.regItemList)
            CustomToast( '---export data to {} success---'.format(openfile_name[0]))
        except Exception as e:
            logger.error('--- save_csv_file ERR: {}! ---'.format(e))
            CustomToast('save_csv_file_Err: {}'.format(e), color='red')
    def savePWFfile(self):
        try:
            openfile_name = QFileDialog.getSaveFileName(self,'保存pwf','','pwf files( *.pwf)')
            with open(openfile_name[0], 'wb') as f_pwf:
                for row_line in range(ioTableList.rowCount()):
                    hexAddr = hex(int(ioTableList.item(row_line, 0).text()) )[2:].zfill(4).encode()
                    hexValue = hex(int(ioTableList.item(row_line, 2).text()))[2:].zfill(4).encode()
                    rawString = binascii.a2b_hex(hexAddr+hexValue)
                    f_pwf.write(rawString)
            CustomToast( '---export data to {} success---'.format(openfile_name[0]))
        except Exception as e:
            logger.error('--- save_pwf_file ERR: {}! ---'.format(e))
            CustomToast('save_pwf_file_Err: {}'.format(e), color='red')
            # 写入多个的地址和值
    def writeItemList(self):
        self.loopWriteFlag = True
        self.loopWriteOneItem()
        # 连续批量写入的地址和值
    def writeBatchList(self):
        addrList = sorted([int(i[0]) for i in self.regItemList])
        if(addrList[-1] - addrList[0] +1) > len(addrList):
            return CustomToast('不是连续的点位, 请检查!')
            # 转呗批量写入的格式化数据
        addr = int(self.regItemList[0][0])
        vals = [i[1] for i in self.regItemList]
        self.writeBuffer = getwriteMulticrc(int(self.stationNum.text().strip()), addr, vals)
        self.edgeNumber = 8
        # 写入多个值，正确的返回长度为8
        self.writeRegVal = vals
        self.writeRegAddr = addr
        self.insertWriteFlag = True
        self.loopWriteBatchFlag = True
        self.send_time.stop()
        self.timerIdx = 0
        self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
        # 连续不间断写入值的方法
    def loopWriteOneItem(self):
        if self.loopWriteIndex >= len(self.regItemList):
            self.statusBar.showMessage('===_loop_write_finish, restart_loop_item_===', 3000)
            self.loopWriteFlag = False
            self.loopWriteIndex = 0
            self.insertWriteFlag = False
            self.receiveWriteFlag = False
            self.send_time.stop()
            self.timerIdx = 0
            if self.serialCom.isOpen():
                return self.loopOneRead()
            addr = int(self.regItemList[self.loopWriteIndex][0])
            val = int(self.regItemList[self.loopWriteIndex][1])
            self.writeBuffer = getwritecrc(int(self.stationNum.text().strip()), addr, val)
            self.edgeNumber = len(self.writeBuffer)
            self.writeRegVal = val
            self.writeRegAddr = addr
            self.insertWriteFlag = True
            self.send_time.stop()
            self.timerIdx = 0
            self.delayTimer.singleShot(100,lambda: self.insertWriteOne(self.writeBuffer) )
    def Com_start_clicked(self):
        self.dock_content.append('=====发送指令channelAddrInfoList_: {}, uuidBinaryMap_: {} ======='.format(self.channelAddrInfoList, self.uuidBinaryMap))
        # 打开波形之前先检测并设置通道，确认之后再打开串口
        # 数据源是通道选择还是地址设置来区分【通道1~N的选择】
        if self.dataTypeList.currentIndex()==0:
            if len(self.multiSelect.get_selected())==0:
                return QMessageBox.critical(self, '严重错误', '未选择通道!')
            rawChannelIndex = [self.regNameList.index(i) for i in self.multiSelect.get_selected()]
            self.settingModeStr = self.settingModeStr[0:4] + format(len(rawChannelIndex), 'b').zfill(4)
            selectedChannelIndex = [hex(i).replace('0x','').zfill(2).upper() for i in rawChannelIndex]
            while len(selectedChannelIndex)<4:
                selectedChannelIndex.append('00')
                if self.dataTypeList.currentIndex()==1:
                    if len(self.channelAddrInfoList)==0:
                        return QMessageBox.critical(self, '严重错误', '未设置地址!')
                    selectedChannelIndex = sum(self.channelAddrInfoList, [])
                    self.settingModeStr = self.settingModeStr[0:4] + format(len(self.channelAddrInfoList), 'b').zfill(4)
                    rawLen = [hex(int(self.settingModeStr, 2)).replace('0x','').upper().zfill(2)]
                    self.dock_content.append('refresh_:{}, sampleCount_:{}'.format(self.samplePeriodNode.text(), self.sampleCountNode.text()))
                    if self.modeTypeList.currentIndex()==0:
                        timeBuffer = re.findall('(.{2})', hex(int(self.samplePeriodNode.text())).replace('0x','').upper().zfill(4))
                        if self.modeTypeList.currentIndex()==1:
                            timeBuffer = re.findall('(.{2})', hex(int(self.sampleCountNode.text())).replace('0x','').upper().zfill(4))
                            self.dock_content.append('===模式_: {}, timeeee_: {}, data_type_: {}, 通道的1~N选择——: {}==='.format(self.modeTypeList.currentText(), timeBuffer, self.dataTypeList.currentText(), selectedChannelIndex) )
                            # 离线模式并且触发模式是自动（上升、下降）的情况下，才会有【触发源设置和触发值】
                            if self.modeTypeList.currentIndex()==1 and self.triggerTypeList.currentIndex()!=0:
                                if not self.triggerInput.text():
                                    return QMessageBox.critical(self, '严重错误', '未设置触发条件!')
                                triggerValList = re.findall('(.{2})', hex(int(self.triggerInput.text())).replace('0x','').upper().zfill(4))
                                triggerSet = [hex(int(self.triggerSource, 2)).replace('0x','').upper().zfill(2) , triggerValList[1], triggerValList[0]]
                                #离线模式并且自动触发时才有触发源这些值
                                self.dock_content.append('triggerValList_:{}, _triggerSet: {}'.format(triggerValList, triggerSet))
                            else:
                                triggerSet = ['00','00','00']
                                salveAddress = hex(int(self.salveAddressNode.text())).replace('0x','').upper().zfill(2)
                                loopTxBuffer = [salveAddress, '16', '00'] + rawLen + timeBuffer + triggerSet + selectedChannelIndex
                                loopTxBufferLen = len(rawLen + timeBuffer + triggerSet + selectedChannelIndex)
                                loopTxBuffer.insert(3, hex(loopTxBufferLen).replace('0x','').upper().zfill(2) )
                                # return# checksum = calc_crc(' '.join(loopTxBuffer))
                                loopTxBuffer += list(checksum)
                                self.dock_content.append('---rawLen: {}, _loopTxBuffer: {}'.format(rawLen, loopTxBuffer))
                                self.sendTxData = binascii.a2b_hex(''.join(loopTxBuffer))
                                self.Com_Send_Data(self.sendTxData)
                                self.mark_rx_cnt = self.wave_rx_cnt
    def execStartResult(self):
        if not self.serialCom.isOpen():
            return QMessageBox.warning(self, self.langData.get('critical_msg'), self.langData.get('serialport_not_opened_msg'))
        self.Com_start_clicked()
        self.heartBeat_Timer.start(1200)
        self.execDelayTimer.singleShot(10,lambda: self.execLoopCommand(3))
    def execStopResult(self):
        if not self.serialCom.isOpen():
            return QMessageBox.warning(self, self.langData.get('critical_msg'), self.langData.get('serialport_not_opened_msg'))
        salveAddress = hex(int(self.salveAddressNode.text())).replace('0x','').upper().zfill(2)
        loopTxBuffer = '{}160000'.format(salveAddress)
        checksum = calc_crc(loopTxBuffer)
        loopTxBuffer += ''.join(checksum)
        self.sendTxData = binascii.a2b_hex(''.join(loopTxBuffer))
        # self.sendTxData = '01 16 00 00 E0 1C'
        # self.sendTxData = b'\x01\x16\x00\x00\xe0\x1c' self.heartBeatCheck()
        self.execDelayTimer.singleShot(10,lambda: self.execLoopCommand(3))
        # 检测关闭监控的指令
    def execLoopCommand(self, repeatCount):
        if repeatCount<1:
            return
        repeatCount-=1
        #重新发送计数递减
        self.Com_Send_Data(self.sendTxData)
        self.execDelayTimer.singleShot(10,lambda: self.execLoopCommand(repeatCount))
    def renderChanneTable(self):
        if not self.selectedChannelMap:
            return QMessageBox.critical(self, self.langData.get('critical_msg'), 'please_select_channel!')
            # 由于这里会触发信号槽，所以我们先阻断信号
        channelTableList.blockSignals(True)
        if self.curveList:
            channelTableList.setRowCount(len(self.selectedChannelMap))
            for (row,item) in enumerate(self.selectedChannelMap):
                addrItem = QTableWidgetItem(item.get('addr',''))
                nameItem = QTableWidgetItem(item.get('name',''))
                nameItem.setToolTip(item.get('name',''))
                addrItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                nameItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                channelTableList.setItem(row, 0, addrItem)
                channelTableList.setItem(row, 1, nameItem)
                colorItem = QTableWidgetItem(item['color'])
                colorItem.setBackground(QBrush(QColor(self.regColorList[row])) )
                channelTableList.setItem(row, 2, colorItem)
            scaleItem = QSpinBox()
            scaleItem.setRange(-99999,99999)
            scaleItem.setProperty('itemRowIndex', row)
            scaleItem.setValue(int(item['scale']))
            scaleItem.setKeyboardTracking(False)
            scaleItem.valueChanged.connect(self.scaleItemValuechange)
            channelTableList.setCellWidget(row, 3, scaleItem)
            offsetItem = QSpinBox()
            offsetItem.setRange(-99999,99999)
            offsetItem.setProperty('itemRowIndex', row)
            offsetItem.setValue(int(item['offset']))
            # offsetItem.setSuffix('Hz')
            offsetItem.setKeyboardTracking(False)
            offsetItem.valueChanged.connect(self.offsetItemValuechange)
            channelTableList.setCellWidget(row, 4, offsetItem)
            xaxbItem = QTableWidgetItem('')
            xaxbItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            channelTableList.setItem(row, 5, xaxbItem)
            yaItem = QTableWidgetItem('')
            yaItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            channelTableList.setItem(row, 6, yaItem)
            ybItem = QTableWidgetItem('')
            ybItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            channelTableList.setItem(row, 7, ybItem)
            yaybItem = QTableWidgetItem('')
            yaybItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            channelTableList.setItem(row, 8, yaybItem)
        else:
            self.dock_content.append('---channelTable_already_render!---')
            channelTableList.blockSignals(False)
            #释放，开始监听信号
    def setChannelCFG(self):
        if not self.selectedChannelMap:
            self.dock_content.append('please_select_channel!')
            return
            # return QMessageBox.critical(self, self.langData.get('critical_msg'), 'please_select_channel!')
        calc_table_heihgt = 80 + 30*len(self.selectedChannelMap)
        if settingDialog.isVisible():
            settingDialog.resize(600, calc_table_heihgt)
            settingDialog.raise_()
        else:
            settingDialog.setGeometry(plotWidDialog.geometry().left(), plotWidDialog.geometry().top()+120, 600,calc_table_heihgt)
            settingDialog.show()
    def scaleItemValuechange(self, scaleVal):
        currentNode = self.sender()
        itemRowIndex = currentNode.property('itemRowIndex')
        self.regScaleList[itemRowIndex]=scaleVal
        self.selectedChannelMap[itemRowIndex]['scale']=str(scaleVal)
        if not self.toggle_plotGraphFlag:
            if self.plotGraphType=='datawave':
                self.refresh_realTimePlot()
            elif self.plotGraphType=='softwave':
                self.refresh_softWavePlot()
    def offsetItemValuechange(self, offsetVal):
        currentNode = self.sender()
        itemRowIndex = currentNode.property('itemRowIndex')
        self.regOffsetList[itemRowIndex]=offsetVal
        self.selectedChannelMap[itemRowIndex]['offset']=str(offsetVal)
        #如果波形停止更新了就手动重绘图形界面
        if not self.toggle_plotGraphFlag:
            if self.plotGraphType=='datawave':
                self.refresh_realTimePlot()
            elif self.plotGraphType=='softwave':
                self.refresh_softWavePlot()
    def setChannelResetClicked(self):
        self.regScaleList = [1]*20
        self.regOffsetList = [0]*20
        self.regColorList = ['#800000','#FF0000','#CD5C5C','#FFA07A','#FF8C00','#FFD700','#B8860B','#EEE8AA','#BDB76B','#808000','#9ACD32', '#6B8E23','#2E8B57','#EEE8AA','#D2691E','#00FFFF','#E0FFFF','#4682B4','#191970','#4169E1','#8A2BE2','#D8BFD8','#FF1493', '#FAEBD7','#8B4513', '#F4A460','#708090','#FFAA00']
        for item in self.selectedChannelMap:
            item['scale'] = '1'
            item['offset'] = '0'
        if not self.toggle_plotGraphFlag:
            if self.plotGraphType=='datawave':
                self.refresh_realTimePlot()
            elif self.plotGraphType=='softwave':
                self.refresh_softWavePlot()
        scaleNodeList = channelTableList.findChildren(QSpinBox)
        for key,scaleNode in enumerate(scaleNodeList):
            scaleNode.blockSignals(True)
            if key%2==0:
                scaleNode.setValue(1)
            if key%2==1:
                scaleNode.setValue(0)
            scaleNode.blockSignals(False)

    def channelItemClick(self,item):
        row,col,text = item.row(), item.column(), item.text()
        if col==2:
            color1 = QColorDialog.getColor()
            if color1.isValid():
                #设置选择的颜色
                self.regColorList[row] = color1.name()
                self.selectedChannelMap[row]['color'] = str(self.regColorList[row])
                #将选择的颜色输出在输入框. item.setText(color1.name())
                item.setBackground(QBrush(QColor(color1.name())) )
                self.curveList[row].setPen(QColor(color1.name()))
    def toggle_plotGraph(self):
        if self.toggle_plotGraphFlag:
            # 已打开波形的勾选，就要重新设置全局的轮询点位
            self.setGroupAddrList(False)
            self.plotGraphFlag = False
            self.toggle_plotGraphFlag = False
            self.togglePlotBtn.setText(self.langData.get('start_display'))
            self.togglePlotBtn.setStyleSheet('background:green')
        else:
            self.createCurves()
            self.toggle_plotGraphFlag = True
            self.togglePlotBtn.setText(self.langData.get('pause_display'))
            self.togglePlotBtn.setStyleSheet('background:red')
            self.customGraph.enableAutoRange()
            if self.toggle_plotGraphFlag:
                self.customGraph.setMouseEnabled(x=False, y=True)
                # 默认禁用X轴操作
                chk_mouseXEnable.setChecked(False)
                chk_mouseYEnable.setChecked(True)
            else:
                self.delayUpdatePosFlag=True
                self.customGraph.setMouseEnabled(x=True, y=False)
                self.customGraph.sigXRangeChanged.connect(self.updatexPosition)
                chk_mouseXEnable.setChecked(True)
                chk_mouseYEnable.setChecked(False)
    def resetWaveChart(self):
        self.customGraph.enableAutoRange()
        self.delayUpdatePosTimer.stop()
        self.delayUpdatePosFlag=False
        self.execDelayTimer.singleShot(500, self.setDelayUpdatePosFlag)
        if self.toggleChannelGridFlag:
            self.renderSoftwavePlot()
    def recordDialogFinished(self):
        self.dock_content.append('关闭弹框_{}'.format(self.sender().windowTitle()) )
        # 关掉弹框的时候，也重开常规轮询的操作
    def faultLogDialogFinished(self):
        self.dock_content.append('关闭弹框_文件记录界面' )
        self.logDialogOpened=False
        if self.serialCom.isOpen():
            self.send_time.start(100)
    def otaDialogFinished(self):
        self.dock_content.append('关闭弹框_OTA升级界面' )
        self.otaDialogOpened=False
        if self.serialCom.isOpen():
            self.send_time.start(100)
            # 关闭弹框的时候也关闭报文的勾选框
    def bufferDialogFinished(self):
        self.dock_content.append('关闭_报文弹框界面' )
        self.toggle_text.setChecked(False)
        self.writeLocalSettings()
    def plotMonitorDialogFinished(self):
        self.dock_content.append('关闭_实时波形界面' )
        self.plotMonitorGraphFlag=False
    def toggle_plotMonitorGraph(self):
        if not self.checkedAddrList or not self.plotGraphType:
            return
        if self.toggle_plotGraphFlag2:
            # 已打开波形的勾选，就要重新设置全局的轮询点位
            self.setGroupAddrList(False)
            self.plotMonitorGraphFlag = False
            self.openSelectBtn.setEnabled(True)
            self.toggle_plotGraphFlag2 = False
            self.togglePlotBtn2.setText(self.langData.get('start_display'))
            self.togglePlotBtn2.setStyleSheet('background:green')
        else:
            self.createMonitorCurves()
            self.toggle_plotGraphFlag2 = True
            self.togglePlotBtn2.setText(self.langData.get('pause_display'))
            self.togglePlotBtn2.setStyleSheet('background:red')
            if self.toggle_plotGraphFlag2:
                self.customPlotGraph.setMouseEnabled(x=False, y=True)
                # 默认禁用X轴操作
                chk2_mouseXEnable.setChecked(False)
                chk2_mouseYEnable.setChecked(True)
            else:
                self.delayUpdatePosFlag=True
                self.customPlotGraph.setMouseEnabled(x=True, y=False)
                self.customPlotGraph.sigXRangeChanged.connect(self.updateMonitorXPosition)
                chk2_mouseXEnable.setChecked(True)
                chk2_mouseYEnable.setChecked(False)
    def set_mouseXEnable2(self):
        self.customPlotGraph.setMouseEnabled(x=chk2_mouseXEnable.isChecked(), y=chk2_mouseYEnable.isChecked())
    def set_mouseYEnable2(self):
        self.customPlotGraph.setMouseEnabled(x=chk2_mouseXEnable.isChecked(), y=chk2_mouseYEnable.isChecked())
    def updateMonitorXPosition(self, vx):
        if self.toggle_plotGraphFlag2:
            return
        xRange = self.customPlotGraph.viewRange()[0]
        rangeStart = round(xRange[0])
        rangeEnd = round(xRange[1])
        self.delayUpdatePosTimer.stop()
        if not self.readHistoryFlag and self.delayUpdatePosFlag:
            if 0< rangeStart < len(self.monitor_graph_y):
                self.rangeStartBorder = rangeStart
                self.rawSlicedData = self.monitor_graph_y[rangeStart: rangeEnd]
                self.refresh_realTimePlot('updateRangeWave')
    def resetMonitorChart(self):
        self.customPlotGraph.enableAutoRange()
        if self.toggleChannelGridFlag:
            self.renderMonitorPlot()
    def setDelayUpdatePosFlag(self):
        self.delayUpdatePosFlag=True
    def getCheckedList(self, mulCheckedList):
        if not mulCheckedList:
            # 先清除界面再添加图例和线条
            self.graph_y=[]
            self.curveList = []
            self.save_graph_y = []
            return
        if len(mulCheckedList) > self.globalCurvesNum:
            return QMessageBox.critical(self, '严重错误', '选择通道数目超限, 请检查配置文件条目数量({})!'.format(self.globalCurvesNum))
        self.selectedChannel = mulCheckedList
        cselectedIndex = [self.regNameList.index(i) +1 for i in mulCheckedList]
        self.checkedChannelList = mulCheckedList
        self.selectedChannelMap = []
        for nx,name in enumerate(mulCheckedList):
            self.selectedChannelMap.append({ 'name': name, 'addr': '', 'color': self.regColorList[nx], 'scale': str(self.regScaleList[nx]), 'offset': str(self.regOffsetList[nx]), })
        self.createCurves()
        self.saveCheckedChannelList()
        self.readHistoryFlag = False
        if settingDialog.isVisible():
            self.setChannelCFG()
            if self.triggerChannelList.isVisible():
                self.triggerChannelList.clear()
                self.triggerChannelList.addItems(self.multiSelect.get_selected())
    def saveCheckedChannelList(self):
        # 选中的通道数据自动保存到csv
        try:
            with open('./config/channelCFG.csv', 'w', encoding='utf_8_sig', newline='') as f:
                f_csv = csv.writer(f)
                f_csv.writerow(['name', 'id', 'scale', 'offset', 'chlChecked'])
            for item in self.regNameInfoList:
                if len(item)==4:
                    item.append('N')
                    if item[0] in self.checkedChannelList:
                        item[4]='Y'
                    else:
                        item[4]='N'
                        f_csv.writerows(self.regNameInfoList)
        except Exception as e:
            logger.error('--- save_export_channel_csv_ERR: {}! ---'.format(e))
            self.statusBar.showMessage('--- save_export_channel_csv_ERR: {}! ---'.format(e), 3000)
            self.statusBar.showMessage('--- Set_Checked_Channel_Success! ---' , 3000)
            # 创建n条曲线，用于画图
    def createMonitorCurves(self):
        if not self.checkedAddrList or not self.plotGraphType:
            return
        self.checkedAddrMap = {keyName:'' for keyName in self.checkedAddrList}
        # self.groupAddrList = []
        # if self.mergeContinuousFlag:
        # contentReadArr = getSliceChunkArr(self.checkedAddrList, self.pollingSize)
        # else:
        # contentReadArr = getSplitArr(self.checkedAddrList, self.pollingSize)
        # if 'title' not in self.currentTab: return QMessageBox.warning(self, self.langData.get('warning_msg'), 'data_err, please_select_channel!' )
        # for splitArr in contentReadArr:
        # self.groupAddrList.append({
        # 'addr': splitArr[0],
        # 'count': len(splitArr),
        # 'title': self.currentTab['title'],
        # 'connect485Id': self.currentTab['connect485Id'],
        # })
        # self.readRegTitle = self.groupAddrList[0].get('title')
        self.dock_content.append('===checkedAddrList_: {}, _checkedAddrMap_: {}==='.format(self.checkedAddrList, self.checkedAddrMap ))
        if self.serialCom.isOpen() and not self.send_time.isActive():
            self.dock_content.append('===create_monitor_curve, looptimer_NOTActive===')
            self.send_time.start(100)
            self.monitor_graph_y = []
            # 先清除界面再添加图例和线条
            self.customPlotGraph.clear()
            self.monitorCurveList = []
            for nx,reg in enumerate(self.checkedAddrList):
                currentCurve = self.customPlotGraph.plot(pen=pg.mkPen(color = self.regColorList[nx]), name = self.channelListMap[reg])
                self.monitorCurveList.append(currentCurve)
            self.plotMonitorGraphFlag = True
            self.openSelectBtn.setEnabled(False)
            self.toggleCursorBtn2.setChecked(False)
            self.customPlotGraph.enableAutoRange()
            for item in self.monitorLegendList.items:
                single_item=item[0]
                label_item=item[1]
                curve = single_item.item
                label_item.mouseClickEvent = lambda ev, c=curve: self.monitorhighlight_curve(c)
                # 已打开波形的勾选，就要重新设置全局的轮询点位
    def createCurves(self):
        if not self.plotGraphType or not self.selectedChannelMap or not plotWidDialog.isVisible():
            return
            # 先清除界面再添加图例和线条
        self.customGraph.clear()
        self.graph_y=[]
        self.save_graph_y=[]
        self.rangeStartBorder=0
        # 先清除界面再添加图例和线条
        self.curveList = []
        for (i, item) in enumerate(self.selectedChannelMap):
            currentCurve = self.customGraph.plot(pen=pg.mkPen(color=item['color']), name=item['name'])
            currentCurve.opts['antialias'] = True
            self.curveList.append(currentCurve)
        self.plotGraphFlag = True
        self.toggleCursorBtn.setChecked(False)
        self.chk_cursor.setChecked(False)
        self.renderChanneTable()
        # 为图例项添加点击事件
        for item in self.legendList.items:
            single_item=item[0]
            label_item=item[1]
            curve = single_item.item
            label_item.mouseClickEvent = lambda ev, c=curve: self.highlight_curve(c)
            # 定义高亮函数
    def highlight_curve(self, selectedCurve):
        # 重置所有曲线的宽度
        # # 设置选中曲线的宽度
        for nx, currentCurve in enumerate(self.curveList):
            if currentCurve == selectedCurve:
                cWidth = 3 if selectedCurve.opts['pen'].width()==1 else 1
                currentCurve.setPen(pg.mkPen(currentCurve.opts['pen'].color(), width=cWidth))
                # 设置坐标轴文字颜色
                cColor = QColor('#ffffff') if selectedCurve.opts['pen'].width()==1 else currentCurve.opts['pen'].color()
                axis_pen = pg.mkPen(cColor, width=cWidth)
                self.customGraph.getAxis('left').setTextPen(axis_pen)
                self.customGraph.getAxis('bottom').setTextPen(axis_pen)
            else:
                currentCurve.setPen(pg.mkPen(currentCurve.opts['pen'].color(), width=1))
    def monitorhighlight_curve(self, selectedCurve):
        for nx, currentCurve in enumerate(self.monitorCurveList):
            if currentCurve == selectedCurve:
                cWidth = 3 if selectedCurve.opts['pen'].width()==1 else 1
                currentCurve.setPen(pg.mkPen(currentCurve.opts['pen'].color(), width=cWidth))
                # 设置坐标轴文字颜色
                cColor = QColor('#ffffff') if selectedCurve.opts['pen'].width()==1 else currentCurve.opts['pen'].color()
                axis_pen = pg.mkPen(cColor, width=cWidth)
                self.customGraph.getAxis('left').setTextPen(axis_pen)
                self.customGraph.getAxis('bottom').setTextPen(axis_pen)
            else:
                currentCurve.setPen(pg.mkPen(currentCurve.opts['pen'].color(), width=1))
    def realTime_DataPlot(self):
        # 取值并赋值给相应的变量
        valList = list(self.checkedAddrMap.values())
        if '' in valList:
            return
        vector_y = [QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss_zzz')] + valList
        self.monitor_graph_y.append(vector_y)
        self.plot_rx_cnt+=1
        plot_rx_label.setText("{}: {}".format(self.langData.get('channel_data_counts'),self.plot_rx_cnt))
        #截取最后N个列表的数据
        self.rawSlicedData = copy.deepcopy(self.monitor_graph_y[-1* int(self.screenWidthNode.text()):])
        self.refresh_realTimePlot()
        # 刷新图像,输出实时数据的图像
    def refresh_realTimePlot(self, type='normal'):
        slicedData = copy.deepcopy(self.rawSlicedData)
        ydata = [[] for i in slicedData[0]]
        if not ydata:
            return
        for itemdata in slicedData:
            for idx,val in enumerate(itemdata):
                ydata[idx].append(val)
        self.timeSlicedData = ydata[0]
        try:
            if type=='updateRangeWave':
                xAxis_len = range(self.rangeStartBorder, len(slicedData) + self.rangeStartBorder)
            else:
                xAxis_len = range( len(self.monitor_graph_y) - len(slicedData), len(self.monitor_graph_y))
                self.rangeStartBorder = len(self.monitor_graph_y) - len(slicedData)
                endXrange = len(self.monitor_graph_y) if len(self.monitor_graph_y) > int(self.screenWidthNode.text()) else int(self.screenWidthNode.text())
                if self.plotMonitorGraphFlag:
                    self.customPlotGraph.setRange(xRange=(len(self.monitor_graph_y) - len(slicedData), endXrange), padding=0)
                    for nx, currentCurve in enumerate(self.monitorCurveList):
                        currentCurve.setData(xAxis_len, ydata[nx+1])
        except Exception as e:
            logger.error('--- update_plot_realTime_data_ERR: {}! ---'.format(e) )
            # 刷新软件示波器数据,输出图像
    def refresh_softWavePlot(self, type='normal'):
        slicedData = copy.deepcopy(self.rawSlicedData)
        try:
            ydata = [[] for i in slicedData[-1]]
            if not ydata:
                return
            for itemdata in slicedData:
                for idx,val in enumerate(itemdata):
                    ydata[idx].append( val * self.regScaleList[idx] + self.regOffsetList[idx] )
            if type=='updateRangeWave':
                xAxis_len = range(self.rangeStartBorder, len(slicedData) + self.rangeStartBorder)
            else:
                xAxis_len = range( len(self.graph_y) - len(slicedData), len(self.graph_y))
                self.rangeStartBorder = len(self.graph_y) - len(slicedData)
                endXrange = len(self.graph_y) if len(self.graph_y) > int(self.cacheLengthNode.text()) else int(self.cacheLengthNode.text())
                if self.plotGraphFlag:
                    # self.customGraph.setXRange(len(self.graph_y) - len(slicedData), endXrange)
                    self.customGraph.setRange(xRange=(len(self.graph_y) - len(slicedData), endXrange), padding=0)
                    for nx, currentCurve in enumerate(self.curveList):
                        currentCurve.setData(xAxis_len, ydata[nx])
        except Exception as e:
            logger.error('--- update_plot_softdata_ERR: {}! ---'.format(e))
    def openSoftWavefile(self):
        if self.plotGraphFlag:
            return QMessageBox.warning(self, self.langData.get('warning_msg'), '请先关掉在线波形，再打开历史数据!' )
        openfile_name = QFileDialog.getOpenFileName(self,'打开csv','','csv file()')
        if len(openfile_name)>0:
            self.globalStatus.setText('fileName: {}'.format(openfile_name[0]))
            if openfile_name[0].endswith('.csv'):
                try:
                    with open (openfile_name[0], 'r', encoding='utf_8_sig') as f:
                        csvdataLines = f.readlines()
                        regArrs = [i.replace('\n','').split(',') for i in csvdataLines]
                        self.openeddataNameList=regArrs.pop(0)
                        #去除头一行的name self.xlsxDataList=[]
                    for x in range(len(self.openeddataNameList)):
                        self.xlsxDataList.append([])
                    for regItem in regArrs:
                        for key,item in enumerate(self.xlsxDataList):
                            item.append(int(regItem[key]))
                    self.toggleChannelGrid(self.openeddataNameList, 'softwaveData')
                    channelDialog.show()
                except Exception as e:
                    logger.error('--- read csv_file ERR: {}! ---'.format(e))
                    self.statusBar.showMessage('--- read csv_file ERR: {}! ---'.format(e), 3000)
                    QMessageBox.critical(self, 'ERR', '--- read csv_file ERR: {}! ---'.format(e))
            elif openfile_name[0].endswith('.xlsx'):
                try:
                    with open(openfile_name[0], 'rb') as f:
                        xlsxData = xl.readxl(f)
                    self.xlsxDataList=[]
                    self.openeddataNameList=[]
                    for ws_name in xlsxData.ws_names:
                        for col in xlsxData.ws(ws=ws_name).cols:
                            self.openeddataNameList.append(col[0])
                            self.xlsxDataList.append(col[1:])
                    self.toggleChannelGrid(self.openeddataNameList, 'softwaveData')
                    channelDialog.show()
                except Exception as e:
                    logger.error('--- read xls_file ERR: {}! ---'.format(e))
                    self.statusBar.showMessage('--- read xls_file ERR: {}! ---'.format(e), 3000)
                    QMessageBox.critical(self, 'ERR', '--- read xlsx_file ERR: {}! ---'.format(e))
                else:
                    QMessageBox.critical(self, '严重错误', '文件格式错误，请检查是否[csv/xlsx]!')
    def openMonitorDatafile(self):
        if self.plotMonitorGraphFlag:
            return QMessageBox.warning(self, self.langData.get('warning_msg'), '请先关掉在线波形，再打开历史数据!' )
        openfile_name = QFileDialog.getOpenFileName(self,'打开csv','','csv file( *.csv)')
        if len(openfile_name)>0:
            try:
                with open (openfile_name[0], 'rt', encoding='utf-8') as f:
                    self.xlsxDataList = []
                self.openeddataNameList = []
                for i,item in enumerate(f.readlines()):
                    lineArr = item.replace('\n','').split(',')
                    if i==0:
                        self.openeddataNameList = lineArr
                        continue
                    self.xlsxDataList.append(lineArr)
                self.toggleChannelGrid(self.openeddataNameList[1:], 'monitorData')
                self.readYdata = [[] for i in self.xlsxDataList[0]]
                for itemdata in self.xlsxDataList:
                    for idx,val in enumerate(itemdata):
                        if idx==0:
                            self.readYdata[idx].append(val)
                        else:
                            self.readYdata[idx].append(float(val) if val!='' else 0)
                            self.timeSlicedData = self.readYdata[0]
                            channelDialog.show()
            except Exception as e:
                logger.error('--- read monitorDatafile_csv_file ERR: {}! ---'.format(e))
                self.statusBar.showMessage('--- read monitorDatafile_csv_file ERR: {}! ---'.format(e), 3000)
                QMessageBox.critical(self, 'ERR', '--- read monitor_csv_file ERR: {}! ---'.format(e))
    def openChannelDialog(self):
        self.renderchannelGrid()
        channelDialog.show()
    def renderchannelGrid(self):
        if self.latestTabIndex == self.tw.currentIndex():
            return
        self.latestTabIndex = self.tw.currentIndex()
        ctabname = self.tw.tabText(self.latestTabIndex)
        currentNodeList = self.regItemNodeMap[ctabname]
        rw_column_Num = 6
        rw_node_count = 0
        self.channelListMap = {}
        currentChannelAddrList = []
        self.channelNodeList = []
        self.checkedAddrList = []
        self.checkedAddrMap = {}
        self.duplicatedIdList = []
        self.filterSearch.clear()
        # 先删除清空原有的条目
        item_list = list(range(self.channelGrid.count()))
        item_list.reverse()
        # 倒序删除，避免影响布局顺序
        for i in item_list:
            item = self.channelGrid.itemAt(i)
            self.channelGrid.removeItem(item)
            if item.widget():
                item.widget().deleteLater()
                # allItemNodeList--->currentNodeList
                for itemNode in currentNodeList:
                    if itemNode.property('attributes')['attr']=='WO':
                        continue
                        #只写的点位跳过
                    self.channelListMap[int(itemNode.property('attributes')['addr'])] = str(itemNode.property('attributes')['name'])
                    currentChannelAddrList.append(itemNode.property('attributes')['addr'])
                    checkNode = QCheckBox( str(itemNode.property('attributes')['name']) )
                    self.filterSearch.addItem( str(itemNode.property('attributes')['name']))
                    checkNode.setProperty('attributes', itemNode.property('attributes'))
                    checkNode.setToolTip( str(itemNode.property('attributes')['addr']) )
                    checkNode.toggled.connect(self.toggle_channelChecked)
                    self.channelGrid.addWidget(checkNode, int(rw_node_count/rw_column_Num), int(rw_node_count%rw_column_Num))
                rw_node_count+=1
                self.channelNodeList.append(checkNode)
                self.channelGrid.setRowStretch(self.channelGrid.rowCount(), 1)
                self.channelGrid.setColumnStretch(self.channelGrid.columnCount(), 1)
                compareArr=list(set(currentChannelAddrList))
                if len(compareArr) != len(currentChannelAddrList):
                    #列表推导式查找重复项
                    repeatList=[n for n in currentChannelAddrList if currentChannelAddrList.count(n) > 1]
                    repeatList=list(set(repeatList))
                    self.dock_content.append('===>通道列表里面存在重复的点位: {}, 请检查!'.format(repeatList))
    def clearCachedGrid(self):
        self.checkedAddrList = []
        self.checkedAddrMap = {}
        self.checkedNameList = []
        self.toggleChannelGridFlag = None
        self.graph_y = []
        self.selectedChannelMap = []
        # 先清除界面再添加图例和线条
        for currentCurve in self.curveList:
            currentCurve.clear()
        self.customGraph.enableAutoRange()
        self.renderchannelGrid()
    def toggleChannelGrid(self, nameList, dataSource='monitorData'):
        # 先删除清空原有的条目
        item_list = list(range(self.channelGrid.count()))
        item_list.reverse()
        # 倒序删除，避免影响布局顺序
        for i in item_list:
            item = self.channelGrid.itemAt(i)
            self.channelGrid.removeItem(item)
            if item.widget():
                item.widget().deleteLater()
                rw_column_Num = 8
                rw_node_count = 0
                self.checkedNameList = []
                self.channelNodeList = []
                self.filterSearch.clear()
                for nodeName in nameList:
                    checkNode = QCheckBox(nodeName)
                    self.filterSearch.addItem(nodeName)
                    checkNode.toggled.connect(self.toggle_checkedChannel)
                    self.channelGrid.addWidget(checkNode, int(rw_node_count/rw_column_Num), int(rw_node_count%rw_column_Num))
                rw_node_count+=1
                self.channelNodeList.append(checkNode)
                self.channelGrid.setRowStretch(self.channelGrid.rowCount(), 1)
                self.channelGrid.setColumnStretch(self.channelGrid.columnCount(), 1)
                self.toggleChannelGridFlag = dataSource
    def toggle_checkedChannel(self):
        node = self.sender()
        curName = node.text()
        if node.isChecked():
            if len(self.checkedNameList)>10:
                return QMessageBox.warning(self, self.langData.get('warning_msg'), '请选择通道的数量不超过10!' )
            if curName not in self.checkedNameList:
                self.checkedNameList.append(curName)
            else:
                if curName in self.checkedNameList:
                    self.checkedNameList.remove(curName)
    def confirmBtnClicked(self):
        channelDialog.close()
        #历史数据来源是软件示波器的还是常规轮询数据
        if self.toggleChannelGridFlag=='softwaveData':
            self.renderSoftwaveCurve()
            return
        if self.toggleChannelGridFlag=='monitorData':
            self.renderMonitorCurve()
            return
        if self.toggle_plotGraphFlag2:
            self.createMonitorCurves()
    def renderMonitorCurve(self):
        self.toggleCursorBtn.setChecked(False)
        self.chk_cursor.setChecked(False)
        self.monitor_graph_y=[]
        self.monitorCurveList = []
        self.customPlotGraph.clear()
        for nx,name in enumerate(self.checkedNameList):
            currentCurve = self.customPlotGraph.plot(pen=pg.mkPen(color=self.regColorList[nx]), name=name)
            self.monitorCurveList.append(currentCurve)
        self.renderMonitorPlot()
        for item in self.monitorLegendList.items:
            single_item=item[0]
            label_item=item[1]
            curve = single_item.item
            label_item.mouseClickEvent = lambda ev, c=curve: self.monitorhighlight_curve(c)
    def renderMonitorPlot(self):
        try:
            xAxis_len = range(0, len(self.xlsxDataList))
            for nx, currentCurve in enumerate(self.monitorCurveList):
                currentCurve.setData(xAxis_len, self.readYdata[nx+1])
            self.customPlotGraph.enableAutoRange()
        except Exception as e:
            logger.error('--- render monitor_data_plot ERR: {}! ---'.format(e))
            QMessageBox.critical(self, self.langData.get('warning_msg'), '--- render monitor_data_plot ERR: {}! ---'.format(e) )
    def renderSoftwaveCurve(self):
        self.selectedChannelMap = []
        # 先清除界面再添加图例和线条
        self.customGraph.clear()
        self.toggleCursorBtn.setChecked(False)
        self.chk_cursor.setChecked(False)
        self.graph_y=[]
        self.save_graph_y=[]
        # 先清除界面再添加图例和线条
        self.curveList = []
        for nx,name in enumerate(self.checkedNameList):
            self.selectedChannelMap.append({ 'name': name, 'addr': '', 'color': self.regColorList[nx], 'scale': str(self.regScaleList[nx]), 'offset': str(self.regOffsetList[nx]), })
            currentCurve = self.customGraph.plot(pen=pg.mkPen(color=self.regColorList[nx]), name=name)
            currentCurve.opts['antialias'] = True
            self.curveList.append(currentCurve)
        self.renderSoftwavePlot()
        for item in self.legendList.items:
            single_item=item[0]
            label_item=item[1]
            curve = single_item.item
            label_item.mouseClickEvent = lambda ev, c=curve: self.highlight_curve(c)
    def renderSoftwavePlot(self):
        try:
            for nx,name in enumerate(self.checkedNameList):
                dataIndex = self.openeddataNameList.index(name)
                xAxis_len = range(0, len(self.xlsxDataList[dataIndex]))
                self.curveList[nx].setData(xAxis_len, self.xlsxDataList[dataIndex])
            self.customGraph.enableAutoRange()
        except Exception as e:
            logger.error('--- render SoftWave_plot ERR: {}! ---'.format(e))
            QMessageBox.critical(self, self.langData.get('warning_msg'), '--- render SoftWavefile_xls_file ERR: {}! ---'.format(e) )
    def resetBtnClicked(self):
        for itemNode in self.channelNodeList:
            itemNode.setChecked(False)
        self.currentTab = {}
        self.duplicatedIdList = []
    def toggleOneChecked(self, txt):
        for itemNode in self.channelNodeList:
            if itemNode.text()==txt:
                if itemNode.isChecked():
                    itemNode.setChecked(False)
                else:
                    itemNode.setChecked(True)
    def toggleOneCheckedByID(self, idx):
        if 0<=idx<=len(self.channelNodeList):
            itemNode = self.channelNodeList[idx]
            if itemNode.isChecked():
                itemNode.setChecked(False)
            else:
                itemNode.setChecked(True)
    def toggle_channelChecked(self):
        node = self.sender()
        curAddr = int(node.property('attributes')['addr'])
        if node.isChecked():
            if len(self.checkedAddrList)>10:
                return QMessageBox.warning(self, self.langData.get('warning_msg'), '请选择通道的数量不超过10!' )
            if self.duplicatedIdList and (node.property('attributes')['item485Id'] not in self.duplicatedIdList):
                return QMessageBox.warning(self, self.langData.get('warning_msg'), '存在不同的通信地址的通道, 请检查!' )
            self.currentTab['title'] = node.property('attributes')['tabTitle']
            self.currentTab['connect485Id'] = node.property('attributes')['item485Id']
            self.duplicatedIdList.append(node.property('attributes')['item485Id'])
            self.duplicatedIdList = list(set(self.duplicatedIdList))
            if curAddr not in self.checkedAddrList:
                self.checkedAddrList.append(curAddr)
            else:
                if curAddr in self.checkedAddrList:
                    self.checkedAddrList.remove(curAddr)
                    if not self.checkedAddrList:
                        self.currentTab = {}
                        self.duplicatedIdList = []
    def toggle_Cursor(self, state):
        if state:
            self.createCursorLine()
        else:
            self.removeCursorLine()
    def removeCursorLine(self):
        if self.cursorLine:
            self.customGraph.removeItem(self.cursorLine)
            if self.showLabel:
                self.customGraph.removeItem(self.showLabel)
                if self.proxy:
                    self.proxy=None
    def createCursorLine(self):
        for item in self.selectedChannelMap:
            self.nameColorMap[item.get('name')] = item.get('color')
            # 设置跟随鼠标移动的线
        self.cursorLine = pg.InfiniteLine(angle=90, movable=False, pen={ 'color':'y', 'width': 1, 'style': Qt.DashLine} )
        self.customGraph.addItem(self.cursorLine, ignoreBounds=True)
        self.showLabel = pg.TextItem()
        self.customGraph.addItem(self.showLabel, ignoreBounds=True)
        # 鼠标移动事件，设置触发函数
        self.proxy = pg.SignalProxy(self.customGraph.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        # 鼠标移动事件，设置触发函数
    def mouseMoved(self, evt):
        pos = evt[0]
        if self.curveList and self.toggleCursorBtn.isChecked() and self.customGraph.sceneBoundingRect().contains(pos):
            mousePoint = self.customGraph.vb.mapSceneToView(pos)
            xindex = round(mousePoint.x())
            y_str='x: {}'.format(xindex)
            #X轴要使用相对坐标，根据X索引来查找Y轴的值
            if self.curveList[0].getData()[0] is None:
                return
            xList = list(self.curveList[0].getData()[0])
            nearestVal, yindex = binary_search_nearest(xList, xindex)
            # 【原文损坏·重建】以下 if 判断及 for 循环体被 HTML 吞掉，按 monitorMouseMoved 的结构推断
            if (0<=yindex) and (yindex<len(xList)):
                for nx, currentCurve in enumerate(self.curveList):
                    yList = currentCurve.getData()[1]
                    yval = int((yList[yindex] - self.regOffsetList[nx]) / self.regScaleList[nx])
                    pheihgt = 14  # 【无法确认】原值丢失
                    y_str += "<br><span style='font-size:{}px;color:{}'>{}: {}</span>".format(pheihgt, self.nameColorMap[currentCurve.name()], currentCurve.name(), yval)
            self.showLabel.setHtml(y_str)
            self.showLabel.setPos(mousePoint.x(), mousePoint.y())
            # 设置光标位置
            self.cursorLine.setPos(mousePoint.x())

    def toggle_Cursor2(self, state):
        if state:
            self.createCursorLine2()
        else:
            self.removeCursorLine2()

    def removeCursorLine2(self):
        if self.cursorLine2:
            self.customPlotGraph.removeItem(self.cursorLine2)
        if self.showLabel2:
            self.customPlotGraph.removeItem(self.showLabel2)
        if self.proxy2:
            self.proxy2 = None

    def createCursorLine2(self):
        self.cursorLine2 = pg.InfiniteLine(angle=90, movable=False, pen={ 'color':'y', 'width': 1, 'style': Qt.DashLine} )
        self.customPlotGraph.addItem(self.cursorLine2, ignoreBounds=True)
        self.showLabel2 = pg.TextItem()
        self.customPlotGraph.addItem(self.showLabel2, ignoreBounds=True)
        # 鼠标移动事件，设置触发函数
        self.proxy2 = pg.SignalProxy(self.customPlotGraph.scene().sigMouseMoved, rateLimit=60, slot=self.monitorMouseMoved)

    def monitorMouseMoved(self, evt):
        pos = evt[0]
        if self.monitorCurveList and self.toggleCursorBtn2.isChecked() and self.customPlotGraph.sceneBoundingRect().contains(pos):
            mousePoint = self.customPlotGraph.vb.mapSceneToView(pos)
            xindex = round(mousePoint.x())
            y_str2 = 'x: {}'.format(xindex)  # 【原文损坏·重建】赋值右侧被吞，按 mouseMoved 推断
            #X轴要使用相对坐标，根据X索引来查找Y轴的值
            if self.monitorCurveList[0].getData()[0] is None:
                return
            xList = list(self.monitorCurveList[0].getData()[0])
            nearestVal, yindex = binary_search_nearest(xList, xindex)
            # 【原文损坏·重建】以下判断与循环体丢失，结构按 mouseMoved 推断
            if (0<=yindex) and (yindex<len(self.timeSlicedData)):
                y_str2 += '<br>{}'.format(self.timeSlicedData[yindex])
                for nx, currentCurve in enumerate(self.monitorCurveList):
                    yList = currentCurve.getData()[1]
                    yval = yList[yindex]
                    pheihgt = 14  # 【无法确认】原值丢失
                    y_str2 += "<br><span style='font-size:{}px;color:{}'>{}: {}</span>".format(pheihgt, self.nameColorMap[currentCurve.name()], currentCurve.name(), yval)
            self.showLabel2.setHtml(y_str2)
            self.showLabel2.setPos(mousePoint.x(), mousePoint.y())
            self.cursorLine2.setPos(mousePoint.x())

    def switchCursor(self, state):  # 【推断】参数名/条件判断被吞
        if state:
            self.createFixedItems()
        else:
            self.removeFixedItems()

    def removeFixedItems(self):
        if self.fixedLine_xa:
            self.customGraph.removeItem(self.fixedLine_xa)
        if self.fixedLine_xb:
            self.customGraph.removeItem(self.fixedLine_xb)
        self.fixedLine_xa = None
        self.fixedLine_xb = None

    def createFixedItems(self):
        self.setChannelCFG()
        self.customGraph.setXRange(0, 100, 0)  # 【推断】参数 "0,100, 0)" 来自损坏文本
        # 获取到xy方向最大范围，然后设置合适的位置
        xRange, yRange = self.customGraph.viewRange()
        xRangeStep = xRange[1] - xRange[0]
        # 【原文损坏】此处 XA 线的创建（pen/label 部分）被吞，按 XB 线的残留格式重建
        self.fixedLine_xa = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen((255,255,0), width=1), label='XA={value:0.0f}', labelOpts={'position': 0.05, 'color': (255,255,0), 'movable': True})
        self.customGraph.addItem(self.fixedLine_xa, ignoreBounds=True)
        self.fixedLine_xb = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen((0,255,0), width=1), label='XB={value:0.0f}', labelOpts={'position': 0.1, 'color': (0,255,0), 'movable': True})
        self.customGraph.addItem(self.fixedLine_xb, ignoreBounds=True)
        self.input_XA_XB.setText(str(round(xRangeStep*0.2)))  # 【无法确认】控件名大小写
        self.input_XA = round(xRange[0] + xRangeStep*0.6)
        self.input_XB = round(xRange[0] + xRangeStep*0.8)
        self.fixedLine_xa.sigDragged.connect(self.handle_sig_dragged_xa)
        self.fixedLine_xb.sigDragged.connect(self.handle_sig_dragged_xb)
        self.fixedLine_xa.setCursor(Qt.SizeHorCursor)  #设置光标为：移动
        self.fixedLine_xb.setCursor(Qt.SizeHorCursor)

    def handle_sig_dragged_xa(self, obj):  # 【推断】函数体仅残留 settingDialog 判断
        if settingDialog.isVisible():
            settingDialog.raise_()
        self.setTableItemValue()

    def handle_sig_dragged_xb(self, obj):  # 【推断】同上
        if settingDialog.isVisible():
            settingDialog.raise_()
        self.setTableItemValue()

    def setTableItemValue(self):
        if settingDialog.isVisible() and (len(self.curveList)>0):  # 【推断】连接词 and 被吞
            for idx in range(len(self.curveList)):
                xaxbItem = QTableWidgetItem(str(self.input_XA-self.input_XB) )
                xaxbItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                channelTableList.setItem(idx, 5, xaxbItem)
            #X轴要使用相对坐标，根据X索引来查找Y轴的值
            if self.curveList[0].getData()[0] is None:
                return
            xList = list(self.curveList[0].getData()[0])
            nearestVala, yindexa = binary_search_nearest(xList, self.input_XA)
            nearestValb, yindexb = binary_search_nearest(xList, self.input_XB)
            if (yindexa>-1) and (yindexb>-1):
                for nx, currentCurve in enumerate(self.curveList):
                    yList = currentCurve.getData()[1]
                    yvalA = int((yList[yindexa] - self.regOffsetList[nx]) /self.regScaleList[nx])
                    yvalB = int((yList[yindexb] - self.regOffsetList[nx]) /self.regScaleList[nx])
                    yaItem = QTableWidgetItem(str(yvalA))
                    yaItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    channelTableList.setItem(nx, 6, yaItem)
                    ybItem = QTableWidgetItem(str(yvalB))
                    ybItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    channelTableList.setItem(nx, 7, ybItem)
                    yaybItem = QTableWidgetItem(str(yvalA - yvalB) )
                    yaybItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    channelTableList.setItem(nx, 8, yaybItem)
    def setChannelAddress(self):
        if addressDialog.isVisible():
            addressDialog.resize(500, 300)
            addressDialog.raise_()
        else:
            addressDialog.setGeometry(plotWidDialog.geometry().left(), plotWidDialog.geometry().top()+120, 500, 300)
            addressDialog.show()
    def addOneBtnClicked(self):
        row_idx = addrTableList.rowCount()
        if row_idx > self.globalCurvesNum:
            return QMessageBox.critical(self, '严重错误', '选择通道数目超限, 请检查配置文件条目数量({})!'.format(self.globalCurvesNum))
        addrTableList.insertRow(row_idx)
        self.latestRowIdx += 1
        uuid = 'ch_{}'.format(self.latestRowIdx)
        self.channelAddrRawMap[uuid] = {'name': '', 'addr': '', 'rawAddr':'', 'scale': '0', 'datatype': '0', 'checked':'Y', 'offset': '0'}
        self.channelAddrInfoMap[uuid] = {'channelAddrs': [], 'typeScale': []}
        self.uuidBinaryMap[uuid]=['','']
        # idItem = QTableWidgetItem(uuid)
        # idItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        # addrTableList.setItem(row_idx, 0, idItem)
        idItem = QCheckBox(uuid)
        idItem.setChecked(True)
        idItem.toggled.connect(self.toggle_checkedAddrChannel)
        addrTableList.setCellWidget(row_idx, 0, idItem)
        nameInputItem = QLineEdit('')
        nameInputItem.setProperty('itemId', uuid)
        nameInputItem.textChanged.connect(self.channelNameEdited)
        addrTableList.setCellWidget(row_idx, 1, nameInputItem)
        addrInputItem = QLineEdit('00000000')
        addrInputItem.setProperty('itemId', uuid)
        addrInputItem.setValidator(QRegExpValidator(QRegExp("^[A-Fa-f0-9]{8}$")))
        addrInputItem.textChanged.connect(self.channelAddrEdited)
        addrTableList.setCellWidget(row_idx, 2, addrInputItem)
        offsetInputItem = QLineEdit('0')
        offsetInputItem.setProperty('itemId', uuid)
        offsetInputItem.setValidator(intValidator)
        offsetInputItem.textChanged.connect(self.channelOffsetEdited)
        addrTableList.setCellWidget(row_idx, 3, offsetInputItem)
        dataTypeItem = QComboBox()
        dataTypeItem.addItem('float', 0)
        dataTypeItem.addItem('u16', 1)
        dataTypeItem.addItem('s16', 2)
        dataTypeItem.setProperty('itemId', uuid)
        dataTypeItem.activated[str].connect(self.selectTypeItem)
        addrTableList.setCellWidget(row_idx, 4, dataTypeItem)
        scaleSetItem = QComboBox()
        scaleSetItem.addItem('0', 0)
        scaleSetItem.addItem('1', 1)
        scaleSetItem.addItem('2', 2)
        scaleSetItem.setProperty('itemId', uuid)
        scaleSetItem.activated[str].connect(self.selectScaleItem)
        addrTableList.setCellWidget(row_idx, 5, scaleSetItem)
        btndelItem = QPushButton('', clicked=self.deleteOneItem)
        btndelItem.setProperty('itemId', uuid)
        btndelItem.setFixedWidth(30)
        btndelItem.setFocusPolicy(Qt.NoFocus)
        btndelItem.setIcon(QIcon('./icons/minusCircle.png'))
        addrTableList.setCellWidget(row_idx, 6, btndelItem)
    def checkAndRenderTable(self):
        row_idx=0
        self.addrdataTypeList=[]
        for uuid,valObj in self.channelAddrRawMap.items():
            self.channelAddrInfoMap[uuid] = {'channelAddrs': [], 'typeScale': []}
            self.channelAddrRawMap[uuid]['name'] = valObj['name']
            self.channelAddrRawMap[uuid]['rawAddr'] = valObj['addr'].zfill(8).upper()
            self.channelAddrRawMap[uuid]['checked'] = valObj['checked']
            self.channelAddrRawMap[uuid]['offset'] = valObj['offset']
            self.uuidBinaryMap[uuid]=['','']
        addrTableList.insertRow(row_idx)
        # idItem = QTableWidgetItem(uuid)
        # idItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        # addrTableList.setItem(row_idx, 0, idItem)
        idItem = QCheckBox(uuid)
        idItem.setChecked(valObj['checked']=='Y')
        idItem.toggled.connect(self.toggle_checkedAddrChannel)
        addrTableList.setCellWidget(row_idx, 0, idItem)
        nameInputItem = QLineEdit(valObj['name'])
        nameInputItem.setProperty('itemId', uuid)
        nameInputItem.textChanged.connect(self.channelNameEdited)
        addrTableList.setCellWidget(row_idx, 1, nameInputItem)
        addrInputItem = QLineEdit(valObj['addr'])
        addrInputItem.setProperty('itemId', uuid)
        addrInputItem.setValidator(QRegExpValidator(QRegExp("^[A-Fa-f0-9]{8}$")))
        addrInputItem.textChanged.connect(self.channelAddrEdited)
        addrTableList.setCellWidget(row_idx, 2, addrInputItem)
        offsetInputItem = QLineEdit(valObj['offset'])
        offsetInputItem.setProperty('itemId', uuid)
        offsetInputItem.setValidator(intValidator)
        offsetInputItem.textChanged.connect(self.channelOffsetEdited)
        addrTableList.setCellWidget(row_idx, 3, offsetInputItem)
        dataTypeItem = QComboBox()
        dataTypeItem.addItem('float', 0)
        dataTypeItem.addItem('u16', 1)
        dataTypeItem.addItem('s16', 2)
        dataTypeItem.setCurrentIndex(int(valObj['datatype']))
        dataTypeItem.setProperty('itemId', uuid)
        dataTypeItem.activated[str].connect(self.selectTypeItem)
        addrTableList.setCellWidget(row_idx, 4, dataTypeItem)
        scaleSetItem = QComboBox()
        scaleSetItem.addItem('0', 0)
        scaleSetItem.addItem('1', 1)
        scaleSetItem.addItem('2', 2)
        scaleSetItem.setCurrentIndex( int(valObj['scale']))
        scaleSetItem.setProperty('itemId', uuid)
        scaleSetItem.activated[str].connect(self.selectScaleItem)
        addrTableList.setCellWidget(row_idx, 5, scaleSetItem)
        btndelItem = QPushButton('', clicked=self.deleteOneItem)
        btndelItem.setProperty('itemId', uuid)
        btndelItem.setFixedWidth(30)
        btndelItem.setFocusPolicy(Qt.NoFocus)
        btndelItem.setIcon(QIcon('./icons/minusCircle.png'))
        addrTableList.setCellWidget(row_idx, 6, btndelItem)
        # 设置初始值放入缓存中去
        cText = hex(int(valObj['offset'])+int(valObj['addr'],16)).replace('0x','').upper().zfill(8)
        self.channelAddrRawMap[uuid]['addr'] = hex(int(valObj['offset'])+int(valObj['addr'],16)).replace('0x','').upper().zfill(8)
        self.channelAddrInfoMap[uuid]['channelAddrs'] = [cText[6:8] , cText[4:6] , cText[2:4] , cText[0:2]]
        self.channelAddrRawMap[uuid]['datatype'] = str(valObj['datatype'])
        self.uuidBinaryMap[uuid][1]=format(int(valObj['datatype']), 'b').zfill(3)
        self.channelAddrRawMap[uuid]['scale'] = str(valObj['scale'])
        self.uuidBinaryMap[uuid][0]=format(int(valObj['scale']), 'b').zfill(3)
        if valObj['checked']=='Y':
            self.addrdataTypeList.append(valObj['datatype'])
            row_idx+=1
            self.latestRowIdx = int(uuid.replace('ch_','')) if (self.latestRowIdx <= int(uuid.replace('ch_',''))) else self.latestRowIdx
            self.channelAddrInfoList = []
            for uuid,val in self.uuidBinaryMap.items():
                formatBinaryVal = ''.join(val).zfill(16)
                self.channelAddrInfoMap[uuid]['typeScale'] = [str(int(formatBinaryVal, 2)).zfill(2)]
                if self.channelAddrRawMap[uuid].get('checked')=='Y':
                    self.channelAddrInfoList.append( self.channelAddrInfoMap[uuid]['channelAddrs'] + self.channelAddrInfoMap[uuid]['typeScale'] )
    def readTableCFG(self):
        if not os.path.exists('./config/addressTableCFG.csv') or addrTableList.rowCount()>0:
            return
        try:
            with open('./config/addressTableCFG.csv', 'rt', encoding='utf-8' ,errors='ignore') as f:
                addrLines = f.readlines()
                regArrs = [i.replace('\ufeff','').replace('\n','').split(',') for i in addrLines]
                regArrs.pop(0)
                #去除头一行的name
                for regItem in regArrs:
                    if regItem[0]=='' or regItem[1]=='' or regItem[2]=='':
                        QMessageBox.critical(self, '严重错误', '地址配置文件的表格中存在空数据(id,name,addr),请检查!')
                        break
                    regItemLen = len(regItem)
                    if regItemLen < 7:
                        regItem.extend(['']*(7 - regItemLen))
                        self.channelAddrRawMap[regItem[0]] = {'name': regItem[1], 'addr': regItem[2], 'datatype': regItem[3], 'scale': regItem[4], 'checked': regItem[5], 'offset': regItem[6] if regItem[6] else '0' }
                        self.checkAndRenderTable()
        except Exception as e:
            logger.error('--- open_addr_csv_ ERR: {}! ---'.format(e))
            self.statusBar.showMessage('--- open_addr_csv_ERR: {}! ---'.format(e), 3000)
            # 打开文件获取点位信息
    def loadChannelList(self):
        if not os.path.exists('./config/channelCFG.csv'):
            return
        try:
            with open ('./config/channelCFG.csv', 'rt', encoding='utf-8') as f:
                self.regNameList = []
                self.regScaleList = []
                self.regOffsetList = []
                self.checkedChannelList = []
                channelLines = f.readlines()
                self.regNameInfoList = [i.replace('\ufeff','').replace('\n','').split(',') for i in channelLines]
                self.regNameInfoList.pop(0)
                #去除头一行的name
                for regItem in self.regNameInfoList:
                    if regItem[0]=='':
                        QMessageBox.critical(self, '严重错误', '配置文件[channelCFG.csv]中存在空数据(name,id),请检查!')
                        break
                    if len(regItem)==2:
                        regItem.append('1')
                    if len(regItem)==3:
                        regItem.append('0')
                    if len(regItem)==4:
                        regItem.append('N')
                    if regItem[4]=='Y':
                        self.checkedChannelList.append(regItem[0])
                    if regItem[0] not in self.regNameList:
                        self.regNameList.append(regItem[0])
                        self.regScaleList.append(1 if regItem[2]=='' else int(regItem[2]))
                        self.regOffsetList.append(0 if regItem[3]=='' else int(regItem[3]))
                while len(self.regColorList) < len(self.regNameList):
                    self.regColorList.append('#D2691E')
                if len(self.regNameInfoList)!=len(self.regNameList):
                    QMessageBox.critical(self, '严重错误', '配置文件[channelCFG.csv]中存在重复的数据(name),请检查!')
        except Exception as e:
            logger.error('--- open_channel_csv__file_ERR: {}---'.format(e))
            self.statusBar.showMessage('---open_channel_csv__file_ERR: {}---'.format(e), 3000)
    def toggle_checkedAddrChannel(self):
        currentNode = self.sender()
        uuid = currentNode.text()
        self.channelAddrRawMap[uuid]['checked'] = 'Y' if currentNode.isChecked() else 'N'
    def channelNameEdited(self):
        currentNode = self.sender()
        uuid = currentNode.property('itemId')
        self.channelAddrRawMap[uuid]['name'] = currentNode.text()
    def channelOffsetEdited(self):
        currentNode = self.sender()
        uuid = currentNode.property('itemId')
        self.channelAddrRawMap[uuid]['offset'] = currentNode.text()
        self.calc_channelAddr(uuid)
    def channelAddrEdited(self):
        currentNode = self.sender()
        uuid = currentNode.property('itemId')
        self.channelAddrRawMap[uuid]['rawAddr'] = currentNode.text()
        self.calc_channelAddr(uuid)
    def calc_channelAddr(self, uuid):
        cOffset = self.channelAddrRawMap[uuid]['offset']
        cAddr = int(self.channelAddrRawMap[uuid]['rawAddr'], 16)
        calc_addr = hex(int(cOffset)+int(cAddr)).replace('0x','').upper().zfill(8)
        self.channelAddrRawMap[uuid]['addr'] = calc_addr
        self.channelAddrInfoMap[uuid]['channelAddrs'] = [calc_addr[6:8] , calc_addr[4:6] , calc_addr[2:4] , calc_addr[0:2]]
        # 下拉框触发事件
    def selectTypeItem(self):
        currentNode = self.sender()
        uuid = currentNode.property('itemId')
        binaryChar=format(int(currentNode.currentData()), 'b').zfill(3)
        self.channelAddrRawMap[uuid]['datatype'] = str(currentNode.currentData())
        self.uuidBinaryMap[uuid][1]=binaryChar
        self.dock_content.append('--datatype---cval: {},_binaryChar: {}'.format( currentNode.currentData(), binaryChar))
    def selectScaleItem(self):
        currentNode = self.sender()
        uuid = currentNode.property('itemId')
        binaryChar=format(int(currentNode.currentData()), 'b').zfill(3)
        self.channelAddrRawMap[uuid]['scale'] = str(currentNode.currentData())
        self.uuidBinaryMap[uuid][0]=binaryChar
        self.dock_content.append('--scale---cval: {},_binaryChar: {}'.format( currentNode.currentData(), binaryChar))
    def deleteOneItem(self):
        currentNode = self.sender()
        uuid = currentNode.property('itemId')
        rowIdx = list(self.uuidBinaryMap.keys()).index(uuid)
        self.dock_content.append('=====deleteidx: {}, _rowIdx:{}'.format( uuid, rowIdx))
        if not uuid in self.uuidBinaryMap:
            return QMessageBox.critical(self, 'KeyError', 'uuid not in uuidBinaryMap, please check!' )
        del self.uuidBinaryMap[uuid]
        del self.channelAddrRawMap[uuid]
        del self.channelAddrInfoMap[uuid]
        addrTableList.removeRow(rowIdx)
        # 24000340
    def settingConfirmEvent(self):
        self.channelAddrInfoList = []
        for uuid,val in self.uuidBinaryMap.items():
            formatBinaryVal = ''.join(val).zfill(16)
            self.channelAddrInfoMap[uuid]['typeScale'] = [str(int(formatBinaryVal, 2)).zfill(2)]
            if self.channelAddrRawMap[uuid].get('checked')=='Y':
                self.channelAddrInfoList.append( self.channelAddrInfoMap[uuid]['channelAddrs'] + self.channelAddrInfoMap[uuid]['typeScale'] )
                # print('====rawBinaryMap_: {}==='.format(self.uuidBinaryMap))
                # print('====channelAddrRawMap_: {}==='.format(self.channelAddrRawMap))
                # print('====channelAddrInfoMap_: {}==='.format(self.channelAddrInfoMap))
                # print('关闭地址弹框===setting=channelAddrInfoList_: {}, uuidBinaryMap_: {}==='.format(self.channelAddrInfoList, self.uuidBinaryMap ))
                if len(self.uuidBinaryMap)>0:
                    self.selectedChannelMap = []
                    currentselectedChannel = list(self.channelAddrInfoMap.keys())
                    for (key,uuid) in enumerate(currentselectedChannel):
                        if self.channelAddrRawMap.get(uuid, {}).get('checked','')!='Y':
                            continue
                        self.selectedChannelMap.append({ 'uuid': uuid, 'addr': self.channelAddrRawMap.get(uuid, {}).get('addr',''), 'name': self.channelAddrRawMap.get(uuid, {}).get('name',''), 'color': self.regColorList[key], 'scale': self.regScaleList[key], 'offset': self.regOffsetList[key], })
                    self.createCurves()
                    self.readHistoryFlag = False
                    if self.triggerChannelList.isVisible():
                        self.triggerChannelList.clear()
                        self.triggerChannelList.addItems(list(self.uuidBinaryMap.keys()))
        # 地址数据保存到csv
        if not self.channelAddrRawMap:
            return
        self.addrdataTypeList = []
        try:
            with open('./config/addressTableCFG.csv', 'w', encoding='utf_8_sig', newline='') as f:
                f_csv = csv.writer(f)
                f_csv.writerow(['id', 'name', 'address', 'datatype', 'datascale', 'chlChecked','offset'])
                for uuid,valObj in self.channelAddrRawMap.items():
                    if valObj['checked']=='Y':
                        self.addrdataTypeList.append(valObj['datatype'])
                    if valObj['name'] and valObj['addr']:
                        f_csv.writerow([uuid, valObj['name'], valObj['rawAddr'], valObj['datatype'], valObj['scale'], valObj['checked'], valObj['offset']])
            self.statusBar.showMessage('--- Set_Addr_Success! ---' , 3000)
        except Exception as e:
            logger.error('--- save export_addr_csv_ ERR: {}! ---'.format(e))
            self.showMessage('--- save export_addr_csv_ERR: {}! ---'.format(e), 3000)
            self.dock_content.append('saved_addrdataTypeList_: ', self.addrdataTypeList )
        addressDialog.close()
        #确定的工作完成后自动关闭弹框
        # 下拉框触发事件 """ 低四位为通道数(_binaryChar) BIT4:数据来源--0:通道选择--1:地址设置 BIT5:数据模式--0:在线模式--1:离线模式 BIT6:触发模式(离线模式有效)--0:手动(收到命令触发一次)--1:自动触发(需要设置触发通道，通道值触发条件等) """
    def selectModeType(self):
        if not self.modeTypeList.isVisible():
            return
        if self.modeTypeList.currentIndex()==0:
            modetype='0'
            self.triggerlabel.hide()
            self.triggerTypeList.hide()
            self.triggerlabel2.hide()
            self.triggerChannelList.hide()
            self.triggerlabel3.hide()
            self.triggerInput.hide()
            refreshLabel.show()
            self.samplePeriodNode.show()
            sampleLabel.hide()
            self.sampleCountNode.hide()
            self.triggerManualBtn.hide()
        else:
            modetype='1'
            self.triggerlabel.show()
            self.triggerTypeList.show()
            # 切换在线离线模式的时候记得要重置一下触发模式
            # self.triggerTypeList.setCurrentIndex(0)
            refreshLabel.hide()
            self.samplePeriodNode.hide()
            sampleLabel.show()
            self.sampleCountNode.show()
            self.triggerManualBtn.show()
            modeList = list(self.settingModeStr)
            modeList[-6] = modetype
            #BIT5对应的是倒数第6项
            self.settingModeStr = ''.join(modeList)
    def selectDataType(self):
        if not self.dataTypeList.isVisible():
            return
        if self.dataTypeList.currentIndex()==0:
            datatype='0'
            self.multiSelect.show()
            self.setAddressBtn.hide()
            if self.triggerChannelList.isVisible() and self.multiSelect.get_selected():
                self.triggerChannelList.clear()
                self.triggerChannelList.addItems(self.multiSelect.get_selected())
            else:
                datatype='1'
                self.multiSelect.hide()
                self.setAddressBtn.show()
                if self.triggerChannelList.isVisible() and self.uuidBinaryMap:
                    self.triggerChannelList.clear()
                    self.triggerChannelList.addItems(list(self.uuidBinaryMap.keys()))
                    modeList = list(self.settingModeStr)
                    modeList[-5] = datatype
                    #BIT4对应的是倒数第5项
                    self.settingModeStr = ''.join(modeList)
    def selectTriggerType(self):
        if not self.triggerTypeList.isVisible():
            return
        if self.triggerTypeList.currentIndex()==0:
            self.triggerlabel2.hide()
            self.triggerChannelList.hide()
            self.triggerlabel3.hide()
            self.triggerInput.hide()
            self.triggerManualBtn.show()
            triggertype='0'
        else:
            self.triggerlabel2.show()
            self.triggerChannelList.show()
            self.triggerlabel3.show()
            self.triggerInput.show()
            self.triggerManualBtn.hide()
            triggertype='1'
            if self.triggerChannelList.count()>0:
                triggerChannelListIndex = self.triggerChannelList.currentIndex()
            else:
                triggerChannelListIndex = 0
                self.triggerSource = format(self.triggerTypeList.currentIndex()-2, 'b').zfill(4) + format(triggerChannelListIndex, 'b').zfill(4)
                modeList = list(self.settingModeStr)
                modeList[-7] = triggertype
                #BIT6对应的是倒数第7项
                self.settingModeStr = ''.join(modeList)
    def triggerManualBtnClicked(self):
        if not self.serialCom.isOpen():
            return self.showMessage(self.langData.get('serialport_not_opened_msg'), 1000)
        self.Com_start_clicked()
        self.execDelayTimer.singleShot(10,lambda: self.execLoopCommand(3))
    def selectTriggerChannel(self):
        currentNode = self.sender()
        self.triggerSource = format(self.triggerTypeList.currentIndex()-2, 'b').zfill(4) + format(currentNode.currentIndex(), 'b').zfill(4)
    def cacheLenRefresh(self):
        cnode = self.sender()
        cnode.clearFocus()
        self.delayTimer.singleShot(100, self.resetWaveChart)
    def setPlotBackground(self):
        currentBG = setPlotBackgroundNode.currentData()
        self.graph_win.setBackground(currentBG)
        # # 设置背景为白色，可以改为其他颜色如 'k' (黑色), 'r' (红色) 等
    def clear_graph_output(self):
        for currentCurve in self.curveList:
            currentCurve.clear()
        self.customGraph.enableAutoRange()
    def clear_monitor_graph(self):
        for currentCurve in self.monitorCurveList:
            currentCurve.clear()
        self.customPlotGraph.enableAutoRange()
    def saveImg_Button_clicked(self):
        fileName = "exportlog/{}/screenshot_{}.png".format(self.currentDate, QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss'))
        self.customGraph.writeImage(fileName)
        self.statusBar.showMessage('---export data to {} success---'.format(fileName), 3000)
    def resetChartGrid(self, state):
        if state:
            self.customGraph.showGrid(x=True, y=True, alpha=0.5)
        else:
            self.customGraph.showGrid(x=False, y=False, alpha=0.5)
    def resetMouseMode(self, state):
        if state:
            self.customGraph.vb.setMouseMode(pg.ViewBox().RectMode)
        else:
            self.customGraph.vb.setMouseMode(pg.ViewBox().PanMode)
    def set_mouseXEnable(self):
        self.customGraph.setMouseEnabled(x=chk_mouseXEnable.isChecked(), y=chk_mouseYEnable.isChecked())
    def set_mouseYEnable(self):
        self.customGraph.setMouseEnabled(x=chk_mouseXEnable.isChecked(), y=chk_mouseYEnable.isChecked())
    def initPlotGraph(self):
        self.graph_win = pg.GraphicsLayoutWidget(self)
        #创建图像窗口
        self.stringaxis = pg.AxisItem(orientation='bottom')
        self.customGraph = self.graph_win.addPlot(row=1, col=1, axisItems={'bottom': self.stringaxis})
        # 创建图像graph0
        # self.customGraph.setMouseEnabled(x=False, y=True)
        # 默认禁用X轴操作,yuyue3-20240728
        # self.customGraph.sigXRangeChanged.connect(self.updatexPosition)
        self.customGraph.showGrid(x=True, y=True, alpha=0.5)
        # 设置x轴和y轴的标签
        # self.customGraph.setLabel('left', 'Y Axis Label', units='A')
        # 设置y轴标签
        # self.customGraph.setLabel('bottom', 'X Axis Label', units='s')
        # 设置x轴标签
        # 设置图例的位置，字体大小，竖向间距等
        self.legendList = self.customGraph.addLegend(offset=(15,1), pen=QColor('#555555'), verSpacing=-3, labelTextSize='9pt')
    def initPlotMonitorGraph(self):
        self.graph_widget = pg.GraphicsLayoutWidget(self)
        #创建图像窗口
        self.customPlotGraph = self.graph_widget.addPlot(row=1, col=1)
        self.customPlotGraph.showGrid(x=True, y=True, alpha=0.5)
        self.monitorLegendList = self.customPlotGraph.addLegend(offset=(15,1), pen=QColor('#555555'), verSpacing=-3, labelTextSize='9pt')
    def updatexPosition(self, vx):
        if self.toggle_plotGraphFlag:
            return
            # #延迟调用getViewRange这个方法，【防抖】连续触发只会调用一次【500毫秒】
            # self.delayUpdatePosTimer.start(50)
        self.getViewRange()
    def getViewRange(self):
        xRange = self.customGraph.viewRange()[0]
        rangeStart = round(xRange[0])
        rangeEnd = round(xRange[1])
        self.delayUpdatePosTimer.stop()
        if not self.readHistoryFlag and self.delayUpdatePosFlag:
            if 0< rangeStart < len(self.graph_y):
                self.rangeStartBorder = rangeStart
                self.rawSlicedData = self.graph_y[rangeStart: rangeEnd]
                self.refresh_softWavePlot('updateRangeWave')
                # 关闭窗口前的处理方法
    def closeEvent(self, event):
        logger.info("Main window closed")
        self.dock_content.append('=======================close_app: {}!======================='.format(QDateTime.currentDateTime().toString('hh:mm:ss')))
        self.saveLoopDataFile()
        self.saveBufferListItem()
        self.writeLocalSettings()
    def readFileTrigger(self):
        openfile_name = QFileDialog.getOpenFileName(self,'打开bin','','bin file( *.bin)')
        try:
            with open (openfile_name[0], 'rb' ) as f:
                # 设置文件路径文本
                self.otaFileInputNode.setText(openfile_name[0])
            fileInfo = QFileInfo(openfile_name[0])
            fileSize = fileInfo.size()
            self.dock_content.append('========file_info: {},---file_Size: {}=============='.format(fileInfo, fileSize))
            # 设置文件长度大小
            self.sizeInputNode.setText(str(fileSize))
            rawContent = f.read()
            rawString = rawContent.hex().upper()
            self.rawByteList = re.findall('(.{2})', rawString)
            self.totalUpdateCount = math.ceil(len(self.rawByteList)/int(self.byteLenInputNode.text()))
            # 计算文件CRC self.file_checksum = calc_crc(' '.join(self.rawByteList))
            self.file_checksum = (self.file_checksum[1], self.file_checksum[0])
            self.crcInputNode.setText('0x{}{}'.format(self.file_checksum[0], self.file_checksum[1]))
            self.header4Byte = rawString[0:8]
        except Exception as e:
            logger.error( '--- read bin_file ERR: {}! ---'.format(e))
            self.statusBar.showMessage( '--- read bin_file ERR: {}! ---'.format(e), 3000)
    def throwOTAerr(self):
        if self.otaDialogOpened:
            if self.otaCurrentCount > 0:
                if self.currentType == 'updaterequest':
                    return self.updateRequestTrigger()
                if self.currentType == 'updateLoop':
                    #某一次发送无响应需要重新发送，但文件包序号不要累加
                    # if self.updateIndex>0: self.updateIndex-=1
                    return self.updateLoopTrigger()
                self.otaResponseTimer.stop()
                CustomToast(self.langData.get('response_fail_msg'))
                self.updateTiptext.setText('')
                # 之前锁定的组件解锁，正常可以使用
                self.otaCurrentCount = 3
                self.devInputNode.setEnabled(True)
                self.otaUpdateList.setEnabled(True)
                self.byteLenInputNode.setEnabled(True)
                self.updateTriggerBtn.setEnabled(True)
                if self.currentType == 'updateLoop':
                    self.updateIndex=0
                    #文件包序号自动清零
                    self.progressbar01.setValue(0)
                    # 设备信息查询的指令
    def getDevInfoTrigger(self):
        if not self.serialCom.isOpen():
            return CustomToast(self.langData.get('serialport_not_opened_msg'))
        self.currentType = 'getdevInfo'
        self.updateTiptext.setText(self.langData.get('update_version_reading'))
        #发送设备信息查询的指令
        slaveID = '{:02x}'.format(int(self.devInputNode.text()))
        devType = '{:02x}'.format(int(self.otaUpdateList.currentText().split('=')[0]))
        loopTxBuffer = binascii.a2b_hex('{}1500{}000100'.format(slaveID, devType))
        self.formatOTABuffer(loopTxBuffer)
        self.delayTimer.singleShot(self.writeWaitTime, self.delayRenderText)
        # 文件下传请求的方法
    def updateRequestTrigger(self):
        if not self.serialCom.isOpen():
            return CustomToast(self.langData.get('serialport_not_opened_msg'))
        if self.sizeInputNode.text()=='' or self.file_checksum=='':
            return CustomToast('please_select_bin_file!' )
        self.updateTriggerBtn.setEnabled(False)
        self.devInputNode.setEnabled(False)
        self.otaUpdateList.setEnabled(False)
        self.byteLenInputNode.setEnabled(False)
        self.currentType = 'updaterequest'
        self.otaCurrentCount -=1
        # 计算文件长度，按照4个字节的格式来定
        # fileSize = '{:02x}'.format(int(self.sizeInputNode.text())).zfill(8)
        # fileSizeList = re.findall('(.{2})', fileSize.upper())
        #发送升级请求的指令
        self.updateTiptext.setText(self.langData.get('update_requesting'))
        slaveID = '{:02x}'.format(int(self.devInputNode.text()))
        devType = '{:02x}'.format(int(self.otaUpdateList.currentText().split('=')[0]))
        loopTxBuffer = binascii.a2b_hex('{}1501{}000C'.format(slaveID, devType))
        # 6-9字节拿来设置文件大小的
        loopTxBuffer += int(self.sizeInputNode.text()).to_bytes(4, byteorder='big')
        # 10-11字节加上文件[CRC]
        loopTxBuffer += binascii.a2b_hex('{}{}'.format(self.file_checksum[0], self.file_checksum[1]))
        # 12-15字节拿来设置文件头部4个字节,【需要翻转一下顺序】
        append4Byte = re.findall('(.{2})', self.header4Byte.upper())
        append4Byte.reverse()
        loopTxBuffer += binascii.a2b_hex(''.join(append4Byte))
        # 16-17字节添加下传文件[包长度]
        loopTxBuffer += int(self.byteLenInputNode.text()).to_bytes(2, byteorder='big')
        # 最后一个加上CRC self.formatOTABuffer(loopTxBuffer)
        self.otaResponseTimer.start(self.writeWaitTime)
        # 文件下传过程的指令
    def updateLoopTrigger(self):
        if not self.otaDialogOpened:
            return
        self.currentType = 'updateLoop'
        self.otaCurrentCount -=1
        self.totalUpdateCount = math.ceil(len(self.rawByteList)/int(self.byteLenInputNode.text()))
        self.updateTiptext.setText('{}: {}/{}'.format(self.langData.get('update_progress'), self.updateIndex, self.totalUpdateCount))
        #发送升级执行的指令
        slaveID = '{:02x}'.format(int(self.devInputNode.text()))
        devType = '{:02x}'.format(int(self.otaUpdateList.currentText().split('=')[0]))
        loopTxBuffer = binascii.a2b_hex('{}1502{}'.format(slaveID, devType))
        # 文件包数据长度默认取值,还要看实际截取的列表长度为准
        byteLenSize = int(self.byteLenInputNode.text())
        # 文件包数据内容
        slicedList = self.rawByteList[self.updateIndex *byteLenSize: (self.updateIndex+1) *byteLenSize]
        byteLenSize = len(slicedList)
        # 如果升级次数超限就中止
        if not slicedList:
            self.statusBar.showMessage('===文件包数据内容已经全部完成写入===', 3000)
            return self.updateCompleteTrigger()
            # 4-5字节添加下传文件[包长度+2]
        loopTxBuffer += int(byteLenSize+2).to_bytes(2, byteorder='big')
        # 6-7字节添加文件包序号
        loopTxBuffer += int(self.updateIndex).to_bytes(2, byteorder='big')
        # 第8个字节开始【文件包数据内容】
        loopTxBuffer += binascii.a2b_hex(''.join(slicedList))
        # 最后一个加上CRC self.formatOTABuffer(loopTxBuffer)
        self.otaResponseTimer.start(self.writeWaitTime)
        #文件包序号自动累加,顺便更新进度条
        # self.updateIndex+=1
        numPercent = round((100*self.updateIndex) / self.totalUpdateCount)
        if numPercent<=100:
            self.progressbar01.setValue(numPercent)
            # 文件下传完成的指令
    def updateCompleteTrigger(self):
        self.currentType = 'updateComplete'
        #发送升级执行的指令
        slaveID = '{:02x}'.format(int(self.devInputNode.text()))
        devType = '{:02x}'.format(int(self.otaUpdateList.currentText().split('=')[0]))
        loopTxBuffer = binascii.a2b_hex('{}1503{}000100'.format(slaveID, devType))
        # self.updateTiptext.setText('已经完成,升级结束')
        self.formatOTABuffer(loopTxBuffer)
        self.otaResponseTimer.start(self.writeWaitTime)
    def formatOTABuffer(self, loopTxBuffer):
        self.historyData = b''
        checksum = calc_byte_crc(loopTxBuffer)
        self.otaTXBuffer = loopTxBuffer + checksum
        self.Com_Send_Data(self.otaTXBuffer)
    def keyupSearchText(self):
        if self.searchResults:
            if self.currentSearchText==self.searchTextBox.text():
                return self.highlightNext()
            else:
                self.resetSelectedTextColor()
                self.searchResults = []
                self.currentResultIndex = -1
                self.currentSearchText = ''
                self.rightList.setExtraSelections([])
        search_text = self.searchTextBox.text()
        if not search_text:
            return
        self.currentSearchText=search_text
        cursor = self.rightList.textCursor()
        cursor.setPosition(0)
        self.rightList.setTextCursor(cursor)
        format = QTextCharFormat()
        format.setBackground(QColor('yellow'))
        while True:
            cursor = self.rightList.document().find(search_text, cursor)
            if cursor.isNull():
                break
            self.searchResults.append(cursor)
            cursor.mergeCharFormat(format)
        CustomToast('found {} items'.format(len(self.searchResults)))
        ''' if(self.rightList.find(search_text,QTextDocument.FindBackward)): #查找后一个 cpt = self.rightList.palette() cpt.setColor(QPalette.Highlight, cpt.color(QPalette.Active,QPalette.Highlight)) self.rightList.setPalette(cpt) '''
    def highlightNext(self):
        if not self.searchResults:
            return
        self.currentResultIndex = (self.currentResultIndex + 1) % len(self.searchResults)
        cursor = self.searchResults[self.currentResultIndex]
        self.rightList.setTextCursor(cursor)
        self.rightList.ensureCursorVisible()
    def resetSelectedTextColor(self):
        format = QTextCharFormat()
        format.setBackground(QColor('white'))
        for cursor in self.searchResults:
            cursor.mergeCharFormat(format)
    def downloadLogEvent(self):
        rwtxt1 = int(readWriteReg.text())
        range1 = readIndexRangeInput.text().strip()
        self.regItemList=[]
        self.alternateReadWriteFlag = True
        self.alternateList = []
        for i in range(16):
            self.alternateList.append(['read', rwtxt1, 1])
            self.alternateList.append(['write', rwtxt1, i ])
            # 使用*运算符实现列表拆解（也称为解包）
            # currentFunction = self.alternateList.pop(0)
            # self.alternateExection(*currentFunction)
        self.alternateIndex = 0
        self.alternateExection()
        # 读写操作交替执行的方法
    def alternateExection(self):
        #历史报文清零
        self.insertReadFlag = False
        self.receiveReadFlag = False
        self.insertWriteFlag = False
        self.receiveWriteFlag = False
        self.send_time.stop()
        self.timerIdx = 0
        if len(self.alternateList)<=0:
            self.regAddrLineMap = {}
            self.alternateIndex = 0
            self.alternateReadWriteFlag = False
            if self.serialCom.isOpen() and not self.insertWriteFlag and not self.insertReadFlag:
                self.loopOneRead()
                return
            currentFunction = self.alternateList.pop(0)
            readOrWrite, addr, val = currentFunction
            self.alternateIndex += 1
            if readOrWrite=='read':
                count = val
                self.readRegAddr = addr
                self.readRegCount = count
                self.edgeNumber = 5 + count *2
                self.insertReadFlag = True
                self.regAddrLineMap = {}
                for ix in range(addr, addr+count):
                    self.regAddrLineMap[ix]=''
                readBuffer = getreadcrc(int(self.rwStationNode.text().strip()), addr, count)
                self.delayTimer.singleShot(100,lambda: self.insertReadList(readBuffer) )
            elif readOrWrite=='write':
                currentValue = val
                self.writeBuffer = getwritecrc(int(self.rwStationNode.text().strip()), addr, currentValue)
                self.edgeNumber = len(self.writeBuffer)
                self.writeRegVal = currentValue
                self.writeRegAddr = addr
                self.writeRegName = addr
                self.insertWriteFlag = True
                self.insertWriteOne(self.writeBuffer)
            else:
                self.dock_content.append('参数有误:{}，请检查！'.format(currentFunction))
    def initSearchAllLog(self):
        recordCountLabel.setText('{}: {}'.format(self.langData.get('record_count'), len(self.logdataMapList)))
        logTableList.setRowCount(len(self.logdataMapList))
        for idx,item in enumerate(self.logdataMapList):
            nameItem=QTableWidgetItem(item['name'])
            nameItem.setToolTip(item['name'])
            nameItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            countItem=QTableWidgetItem(item['count'])
            countItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            lengthItem=QTableWidgetItem(item['fileLength'])
            lengthItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            time1Item=QTableWidgetItem(item['startTime'])
            time1Item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            time2Item=QTableWidgetItem(item['endTime'])
            time2Item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            logTableList.setItem(idx,0,nameItem)
            logTableList.setItem(idx,1,countItem)
            logTableList.setItem(idx,2,lengthItem)
            logTableList.setItem(idx,3,time1Item)
            logTableList.setItem(idx,4,time2Item)
        btnItem1 = QPushButton(self.langData.get('file_read_btn1'), clicked=self.startFileUpload)
        btnItem1.setProperty('itemRowIndex', idx)
        btnItem1.setFocusPolicy(Qt.NoFocus)
        btnItem1.setFixedWidth(60)
        logTableList.setCellWidget(idx, 5, btnItem1)
    def formatLoopTxBuffer(self, loopTxBuffer):
        loopTxBufferLen = (len(loopTxBuffer[6:])).to_bytes(2, byteorder='big')
        sendByteBuffer = loopTxBuffer[0:4] + loopTxBufferLen + loopTxBuffer[6:]
        checksum = calc_byte_crc(sendByteBuffer)
        sendByteBuffer += checksum
        self.logTXBuffer = sendByteBuffer
        self.historyData = b''
        self.Com_Send_Data(sendByteBuffer)
        self.logResponseTimer.start(self.writeWaitTime)
    def throwLOGerr(self):
        if self.logDialogOpened and not self.historyData:
            CustomToast(self.langData.get('read_fail_msg'))
            self.logResponseTimer.stop()
    def filterSearchAllLog(self):
        if not self.serialCom.isOpen():
            return CustomToast(self.langData.get('serialport_not_opened_msg'))
        self.currentFileLogType = 'getFileInfoList'
        self.logdataMapList=[]
        logTableList.clearContents()
        logTableList.setRowCount(0)
        recordCountLabel.setText('{}: {}'.format(self.langData.get('record_count'), len(self.logdataMapList)))
        slaveID = '{:02x}'.format(int(logIDInputNode.text().strip()))
        loopTxBuffer = binascii.a2b_hex('{}151000000101'.format(slaveID))
        self.formatLoopTxBuffer(loopTxBuffer)
    def delayRenderFileList(self):
        checksum = calc_byte_crc(self.historyData[:-2])
        if not self.historyData.endswith(checksum):
            self.dock_content.append('=== 文件汇总信息查询0x10: {}, CRC Not Right ==='.format(self.historyData))
            return
        fileTotalCount = self.historyData[6]
        if fileTotalCount==0:
            recordCountLabel.setText( '当前无记录文件')
            return
        self.historyData = self.historyData[7:]
        self.logdataMapList = []
        self.rawBufferMapList = []
        while len(self.historyData)>32 and fileTotalCount>0:
            fileTotalCount-=1
            # 使用 decode() 方法将字节串解码为字符串。
            fileName=self.historyData[0:32].decode('utf-8')
            recordCount = str(int.from_bytes(self.historyData[32:36], byteorder='big'))
            fileLength = str(int.from_bytes(self.historyData[36:38], byteorder='big'))
            if self.historyData[38:42]:
                fstartTime = TimestampToRTC(int.from_bytes(self.historyData[38:42], byteorder='big'))
            else:
                fstartTime='---'
                if self.historyData[42:46]:
                    fendTime = TimestampToRTC(int.from_bytes(self.historyData[42:46], byteorder='big'))
                else:
                    fendTime='---'
                    self.rawBufferMapList.append({'filename': self.historyData[0:32], 'fileCount': self.historyData[32:36], 'fileLength': self.historyData[36:38], 'starttime': self.historyData[38:42], 'endtime': self.historyData[42:46]})
                    self.logdataMapList.append({'id': len(self.logdataMapList), 'name': fileName, 'count': recordCount, 'fileLength': fileLength, 'startTime': fstartTime, 'endTime': fendTime})
                    self.historyData = self.historyData[46:]
                    self.initSearchAllLog()
                    self.currentFileLogType=''
    def formatDateTime(self, dateTime):
        return { 'year': dateTime.date().year(), 'month': dateTime.date().month(), 'day': dateTime.date().day(), 'hour': dateTime.time().hour(), 'minute': dateTime.time().minute(), 'second': dateTime.time().second() }
    def handleHeaderClicked(self, cRowIndex):
        self.setFilterNodeText(cRowIndex)
    def onLogCellClicked(self, cRowIndex, column):
        self.setFilterNodeText(cRowIndex)
    def setFilterNodeText(self, cRowIndex):
        cdata = self.logdataMapList[cRowIndex]
        filterNameNode.setText(cdata.get('name').replace('\0', ''))
        filterNameNode.setCursorPosition(0)
        # 使用 QDateTime 的 fromString 方法将字符串转换为 QDateTime 对象
        startdatatime = QDateTime.fromString(cdata.get('startTime'), "yyyy-MM-dd HH:mm:ss")
        enddatatime = QDateTime.fromString(cdata.get('endTime'), "yyyy-MM-dd HH:mm:ss")
        filterTime1Node.setDateTime(startdatatime)
        filterTime2Node.setDateTime(enddatatime)
        self.crawBuffer = self.rawBufferMapList[cRowIndex]
        self.recordfileName = self.logdataMapList[cRowIndex].get('name').replace('\0', '')
    def startFileUpload(self):
        # 第一步先获取点击的行号，设置文件详情的文件名和开始结束时间等节点，第二部执行文件上传请求等操作
        cRowIndex = self.sender().property('itemRowIndex')
        self.setFilterNodeText(cRowIndex)
        starttime = self.crawBuffer.get('starttime')
        endtime = self.crawBuffer.get('endtime')
        self.execFileUpload(starttime, endtime)
    def stopFileUpload(self):
        self.logResponseTimer.stop()
        self.stopFilePackageFlag = True
    def startFilterUpload(self):
        # 格式化处理选择时间的组件【先得到年月日时分秒，再转为为时间戳，4字节的十六进制，才可以带入使用】
        t1 = self.formatDateTime(filterTime1Node.dateTime())
        t2 = self.formatDateTime(filterTime2Node.dateTime())
        filterStartTime = RTCToTimestamp(t1).to_bytes(4, byteorder='big')
        filterEndTime = RTCToTimestamp(t2).to_bytes(4, byteorder='big')
        self.dock_content.append('t1: {}, t2:{}, filterStartTime_:{}, filterEndTime_:{}'.format(t1, t2, filterStartTime, filterEndTime))
        if filterNameNode.text()=='' or not self.crawBuffer:
            return CustomToast('文件信息不能为空, 请检查!')
        self.execFileUpload(filterStartTime, filterEndTime)
    def execFileUpload(self, starttime, endtime):
        # 文件头部预留64字节，不足的补零【包括文件名称、记录长度、文件大小和预留站位】
        self.prependFileHeader = self.fileUniqueCode + self.crawBuffer.get('filename') + self.crawBuffer.get('fileLength')
        self.currentFileLogType = 'getFileRequest'
        slaveID = '{:02x}'.format(int(logIDInputNode.text().strip()))
        loopTxBuffer = binascii.a2b_hex('{}1511000001'.format(slaveID))
        loopTxBuffer += self.crawBuffer.get('filename')
        # 文件查找方式【第38个字节,m默认先按照时间上传---预留的字段】
        # 0:全部上传
        # 1:按时间上传
        # 2:按索引号上传
        # 3:按最新记录数上传
        loopTxBuffer += b'\x01'
        #先默认是1【按时间上传】
        loopTxBuffer += starttime
        loopTxBuffer += endtime
        # 每包文件最长长度
        unitPackageLen = int(unitPackageLenNode.text()) if unitPackageLenNode.text() else 0
        if not(0< unitPackageLen < 65535):
            return CustomToast('每包文件最长长度{}, 不应超出范围0~65535, 请检查!'.format(unitPackageLen))
        loopTxBuffer += (unitPackageLen).to_bytes(2, byteorder='big')
        self.formatLoopTxBuffer(loopTxBuffer)
    def delayRenderFileInfo(self):
        checksum = calc_byte_crc(self.historyData[:-2])
        if not self.historyData.endswith(checksum):
            self.dock_content.append('=== 文件上传请求0x11: {}, CRC Not Right ==='.format(self.historyData))
            return
        ackNum = self.historyData[6]
        ackNumMap = {0:'未找到上传文件', 1:'找到上传文件', 2:'开始时间错误', 3:'结束时间错误', 4:'文件无记录'}
        self.fileTotalLen = int.from_bytes(self.historyData[7:11], byteorder='big')
        #文件总长度
        self.filePackageLen = int.from_bytes(self.historyData[11:13], byteorder='big')
        #每包长度数
        self.fileDataMode = self.historyData[13]
        #文件数据模式【大端1或者小端0】
        self.prepareFileUpload()
        if ackNum!=1:
            return CustomToast('文件请求异常: {},请检查!'.format(ackNumMap[ackNum]))
        if self.fileDataMode!=0 and self.fileDataMode!=1:
            return CustomToast('文件数据模式异常: {},请检查!'.format(self.fileDataMode))
        if self.fileTotalLen==0 or self.filePackageLen==0:
            return CustomToast('file_package_len_err, 文件总长度:{}, 每包文件长度:{}'.format(self.fileTotalLen,self.filePackageLen))
        else:
            self.getFilePackageList()
    def initFileLogParams(self):
        self.currentFileLogType = 'getFileInfoList'
        self.logdataMapList=[]
        logTableList.clearContents()
        logTableList.setRowCount(0)
        recordCountLabel.setText('{}: {}'.format(self.langData.get('record_count'), len(self.logdataMapList)))
        self.filePackageIndex = 0
        filePackageIdxLabel.setText('{}:{}'.format(self.langData.get('file_package_idx'), self.filePackageIndex))
        filterNameNode.setText('')
        # filterTime1Node.setDateTime(QDateTime.currentDateTime())
        # filterTime2Node.setDateTime(QDateTime.currentDateTime())
        self.crawBuffer = ''
        self.fileDataMode = 1
        #默认大端
        filePathInput1.setText('')
        filePathInput2.setText('')
        filePathInput3.setText('')
        detailList.clear()
        self.recordfileName = ''
        self.parserRawstr = ''
        #记录文件的解析之前的内容
        self.parserTitleMap = {}
        self.parserfileList = []
        self.parserRawstrList = []
        self.parserRawstrListCopy = []
        self.ruleMatchedFlag = True
    def prepareFileUpload(self):
        self.filePackageIndex = 0
        self.filePackageAccLen = 0
        #文件长度，用于累计计算
        # 文件头部预留64字节，不足的补零【包括文件名称、记录长度、文件大小和预留站位】
        self.fileRawDataContent = b''
        self.progressbar03.setValue(self.progressbar03.minimum())
        self.currentFileLogType=''
        self.stopFilePackageFlag = False
    def getFilePackageList(self):
        if self.stopFilePackageFlag:
            self.logResponseTimer.stop()
            detailList.addItem('===文件上传已经停止!===')
            detailList.item(detailList.count() -1).setForeground(QColor('red'))
            return
        self.currentFileLogType = 'getFilePackage'
        slaveID = '{:02x}'.format(int(logIDInputNode.text().strip()))
        loopTxBuffer = binascii.a2b_hex('{}1512000001'.format(slaveID))
        # 6-7字节请求文件包序号(0开始)
        loopTxBuffer += (self.filePackageIndex).to_bytes(2, byteorder='big')
        self.formatLoopTxBuffer(loopTxBuffer)
    def delayRenderFileDetail(self):
        checksum = calc_byte_crc(self.historyData[:-2])
        if not self.historyData.endswith(checksum):
            self.dock_content.append('=== 文件上传过程0x12: {}, CRC Not Right ==='.format(self.historyData))
            return
        if len(self.historyData)<22:
            detailList.addItem('===file_length_err, bufferData_:{}==='.format(self.historyData))
            detailList.item(detailList.count() -1).setForeground(QColor('red'))
            return CustomToast('file_length_err')
        stateNum = self.historyData[6]
        #上传状态
        filePackIdx = int.from_bytes(self.historyData[7:11], byteorder='big')
        #文件包序号
        firstRecordData = self.historyData[11:]
        #第一条记录数据
        firstRecordData = firstRecordData[:-2]
        #去除本包文件末尾的CRC
        if not firstRecordData:
            return CustomToast('文件内容为空, 请检查!')
        self.fileRawDataContent += firstRecordData
        self.filePackageAccLen += len(firstRecordData)
        if filePackIdx!=self.filePackageIndex:
            detailList.addItem('===文件包序号异常, cidx: {}, pkg_idx: {}==='.format(filePackIdx, self.filePackageIndex ))
            detailList.item(detailList.count() -1).setForeground(QColor('red'))
            if stateNum==1:
                self.autoSaveUpFile()
                self.progressbar03.setValue(self.progressbar03.maximum())
                self.delayTimer.singleShot(3000, self.prepareFileUpload)
                return
            self.filePackageIndex = filePackIdx+1
            # detailList.addItem('===文件包序号: {},==='.format(self.filePackageIndex))
            filePackageIdxLabel.setText('{}:{}'.format(self.langData.get('file_package_idx'), self.filePackageIndex))
            detailList.scrollToBottom()
            self.currentFileLogType=''
            #文件包序号自动累加,顺便更新进度条【注意：大于100的时候说明，预估进度不一致则显示99%未完成】
            numPercent = round((100*self.filePackageAccLen) / self.fileTotalLen)
            if numPercent>=100:
                numPercent=99
                self.progressbar03.setValue(numPercent)
                # 开始下一次的文件内容请求
                self.getFilePackageList()
    def autoSaveUpFile(self):
        rawFileLen = round(self.filePackageAccLen).to_bytes(4, byteorder='big')
        rawfileDataMode = round(self.fileDataMode).to_bytes(1, byteorder='big')
        self.prependFileHeader += rawFileLen
        self.prependFileHeader += rawfileDataMode
        self.prependFileHeader += (64 - len(self.prependFileHeader)) * bytes.fromhex('00')
        fileLength = int.from_bytes(self.crawBuffer.get('fileLength'), byteorder='big')
        # 需要计算两个数是否整除，可以使用取模运算符 % 来检查余数是否为零
        if (len(self.fileRawDataContent) % fileLength) !=0:
            return CustomToast('记录文件总长度和记录长度不匹配,总长度应当是记录长度的整数倍,请检查!', timeout=5000)
        try:
            currentTime = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh_mm_ss')
            self.loadFileName = '{}_out_{}'.format(self.recordfileName, currentTime)
            fileName ='exportlog/uploadfile/{}.rcf'.format(self.loadFileName)
            with open(fileName, 'wb') as f:
                rawData = self.prependFileHeader + self.fileRawDataContent
                f.write(rawData)
                # 记录文件的数据加入到缓存中去
            filePathInput1.setText(fileName)
            slicedLength = int.from_bytes(self.prependFileHeader[36:38], byteorder='big')
            self.parserRawstrList = split_bytes(self.fileRawDataContent, slicedLength)
            self.parserRawstrListCopy = split_bytes(self.fileRawDataContent, slicedLength)
            detailList.addItem('===文件名: {}, 文件大小: {}, 文件数据模式:{}, 记录文件总长度: {}, 记录长度: {}, 记录数:{}==='.format(self.recordfileName, len(rawData), {1:'大端', 0:'小端'}[self.fileDataMode], len(self.fileRawDataContent),slicedLength, len(self.parserRawstrList) ) )
            detailList.addItem('===文件传输完成, 保存路径: {}---'.format(fileName))
            detailList.item(detailList.count() -1).setForeground(QColor('green'))
            detailList.scrollToBottom()
            parsetLengthList = list(set([len(i) for i in self.parserRawstrList]))
            if len(parsetLengthList)>1:
                detailList.addItem('===记录文件总长度和记录长度不匹配,总长度应当是记录长度的整数倍,请检查!===' )
                if not self.parserTitleMap:
                    self.autoLoadParseFile()
                    #自动读取文件夹下面的解析规则文件
        except Exception as e:
            logger.error('---err: write_upload_file Err!---', e)
    def finishFileUpload(self):
        slaveID = '{:02x}'.format(int(logIDInputNode.text().strip()))
        loopTxBuffer = binascii.a2b_hex('{}151300000100'.format(slaveID))
        self.formatLoopTxBuffer(loopTxBuffer)
        self.currentFileLogType = 'finishFileInfo'
    def delayRenderFileFinish(self):
        self.dock_content.append('===文件上传完成0x13: {}, raw_fielinfo_hisdata: '.format(self.historyData))
        if not self.historyData or len(self.historyData)<12:
            return CustomToast('data_err')
        if self.historyData==self.logTXBuffer:
            detailList.addItem('===file_upload_finished!===')
            CustomToast('===file_upload_finished!===')
            self.currentFileLogType=''
    def loadParseLog(self):
        openfile_name = QFileDialog.getOpenFileName(self,'打开记录文件', './exportlog/uploadfile','rcf file( *.rcf)')
        try:
            with open (openfile_name[0], 'rb' ) as f:
                filePathInput1.setText(openfile_name[0])
            self.loadFileName = openfile_name[0].split('/')[-1].replace('.rcf','')
            rawContent = f.read()
            self.prependFileHeader = rawContent[0:64]
            if self.fileUniqueCode != self.prependFileHeader[0:4]:
                return CustomToast('文件格式非法[唯一标识符对应不上], 请检查!')
            self.recordfileName = self.prependFileHeader[4:36].replace(b'\x00', b'').decode('utf-8')
            slicedLength = int.from_bytes(self.prependFileHeader[36:38], byteorder='big')
            self.parserRawstrList = split_bytes(rawContent[64:], slicedLength)
            self.parserRawstrListCopy = split_bytes(rawContent[64:], slicedLength)
            self.fileDataMode = int.from_bytes(self.prependFileHeader[38:39], byteorder='big')
            # fileSize = QFileInfo(openfile_name[0]).size()
            detailList.addItem('===文件名: {}, 文件大小: {}, 文件数据模式:{}, 记录文件总长度: {}, 记录长度: {}, 记录数:{}==='.format(self.recordfileName, len(rawContent), {1:'大端', 0:'小端'}[self.fileDataMode], len(rawContent),slicedLength, len(self.parserRawstrList) ) )
            detailList.scrollToBottom()
            parsetLengthList = list(set([len(i) for i in self.parserRawstrList]))
            if len(parsetLengthList)>1:
                return CustomToast('记录文件总长度和记录长度不匹配,总长度应当是记录长度的整数倍,请检查!', timeout=5000)
            if self.fileDataMode!=0 and self.fileDataMode!=1:
                return CustomToast('文件数据模式异常: {},请检查!'.format(self.fileDataMode), timeout=5000)
            if self.recordfileName and self.parserTitleMap:
                if self.recordfileName in self.parserTitleMap:
                    self.parserfileList = copy.deepcopy(self.parserTitleMap[self.recordfileName])
                else:
                    return CustomToast('找不到对应的解析文件,请检查!', timeout=5000)
                if not self.parserTitleMap:
                    self.autoLoadParseFile()
                    #自动读取文件夹下面的解析规则文件
        except Exception as e:
            logger.error('--- read_raw_file_txt_ERR: {}! ---'.format(e))
    def autoLoadParseFile(self):
        # 找到当前文件夹目录下面的配置文件,并开始读取
        if not os.path.exists('./config/downloadCFG'):
            return CustomToast('缺少配置文件[./config/downloadCFG/],请检查!', timeout=5000)
            # 获取指定目录下的所有文件
        fileitems = os.listdir('./config/downloadCFG')
        all_files = ['{}/config/downloadCFG/{}'.format(os.getcwd(), item) for item in fileitems if os.path.isfile(os.path.join('./config/downloadCFG', item))]
        # 遍历文件夹下面所有的解析文件，找到匹配的tab名和文件名一致的就停止解析
        for file in all_files:
            if not self.parserfileList:
                self.loadParseRule(file, 'auto')
                # 自动执行按规则转换记录的方法
                if not self.parserfileList:
                    detailList.addItem('===在解析文件中匹配不到记录文件名: {},请检查!==='.format(self.recordfileName))
                    detailList.item(detailList.count() -1).setForeground(QColor('red'))
    def manualLoadParseFile(self):
        # 找到当前文件夹目录下面的配置文件,并开始读取
        if not os.path.exists('./config/downloadCFG'):
            return CustomToast('缺少配置文件[./config/downloadCFG/],请检查!', timeout=5000)
        openfile_name = QFileDialog.getOpenFileName(self,'打开解析文件', './config/downloadCFG','excel file( *.xlsx)', options = QFileDialog.Options())
        if openfile_name:
            self.loadParseRule(openfile_name[0])
    def loadParseRule(self, fname, cmode='manual'):
        try:
            with open(fname, 'rb') as f:
                parserFileData = xl.readxl(f)
                if self.recordfileName and (self.recordfileName not in parserFileData.ws_names):
                    if cmode=='manual':
                        return CustomToast('在解析文件: {}中匹配不到记录文件名: {},请检查!'.format(fname,self.recordfileName), timeout=5000)
                    else:
                        self.dock_content.append('===在解析文件: {}中匹配不到记录文件名: {},请检查!==='.format(fname,self.recordfileName))
                        return filePathInput2.setText(fname)
                    self.parserTitleMap = {}
                    for ws_name in parserFileData.ws_names:
                        contentItemArr=[]
                        for (line,regItem) in enumerate(parserFileData.ws(ws=ws_name).rows):
                            if line<2:
                                continue
                            regItemLen = len(regItem)
                            if regItemLen < 4:
                                regItem.extend(['']*(4 - regItemLen))
                                itemObj = { 'name': regItem[0] if regItem[0] else 'RESERVED', 'dataType': regItem[1], 'decimalPlace': int(regItem[2]) if regItem[2] else 0, 'repeatFlag': True if regItem[3]=='Y' else False, 'rawArr': [] }
                                contentItemArr.append(itemObj)
                                self.parserTitleMap[ws_name] = contentItemArr
                                if self.recordfileName and self.recordfileName in self.parserTitleMap:
                                    self.parserfileList = copy.deepcopy(self.parserTitleMap[self.recordfileName])
                                    detailList.addItem('===匹配到解析文件,文件名{}===='.format(self.recordfileName) )
        except Exception as e:
            logger.error('--- read_parser_file_parameter_xlsx_ERR: {}! ---'.format(e))
            CustomToast('---read_parser_file_parameter_xlsx_ERR: {}! ---'.format(e))
    def openFileLogDir(self):
        os.startfile( os.getcwd()+'/exportlog/outputfile')
    def parseAndSaveLog(self):
        if filePathInput1.text()=='':
            return CustomToast('未选择记录文件,请检查!')
        if filePathInput2.text()=='':
            return CustomToast('未选择解析文件,请检查!')
        if self.recordfileName and self.parserTitleMap:
            if self.recordfileName in self.parserTitleMap:
                self.parserfileList = copy.deepcopy(self.parserTitleMap[self.recordfileName])
            else:
                return CustomToast('找不到对应的解析文件,请检查!')
            if not self.parserfileList:
                detailList.addItem('===parserRawstrList_:{}, parserfileList_:{}==='.format(self.parserRawstrList, self.parserfileList))
                return CustomToast('找不到对应的解析文件,请检查!')
                # return QMessageBox.critical(self, self.langData.get('critical_msg'), '---解析长度和记录长度不匹配,请检查! ---' )
                # 检测对应解析文件列表中的每个字段的属性【是否重复读取赋值，如果全部否就只需要过一遍，否则循环遍历需要重复赋值的列表】
            repeatflagList = [ it['repeatFlag'] for it in self.parserfileList]
            self.ruleMatchedFlag = True
            if not any(repeatflagList):
                while len(self.parserRawstrList)>0:
                    if not self.ruleMatchedFlag:
                        self.dock_content.append('parserFileHandler_break!!!')
                        break
                    self.parserRawstr = self.parserRawstrList.pop(0)
                    self.parserRawstrLen = len(self.parserRawstr)
                    self.accSlicedLen = 0
                    self.parserfileHandler(True)
                else:
                    while len(self.parserRawstrList)>0:
                        self.parserRawstr = self.parserRawstrList.pop(0)
                        self.parserRawstrLen = len(self.parserRawstr)
                        self.accSlicedLen = 0
                        #添加一个累计解析的字节的长度，用于记录对比
                        if not self.ruleMatchedFlag:
                            self.dock_content.append('outer, parserFileHandler_break!!!')
                            break
                        self.parserfileHandler(True)
                        while len(self.parserRawstr)>0:
                            if not self.ruleMatchedFlag:
                                self.dock_content.append('inner, parserFileHandler_break!!!')
                                break
                            self.parserfileHandler(False)
                            # 处理完成开始保存为文件
                            if len(self.parserRawstrList)>0 or len(self.parserRawstr)>0:
                                self.ruleMatchedFlag=False
                                if not self.ruleMatchedFlag:
                                    self.dock_content.append('===异常情况, rawlist: {}, rawStr: {}, 仍然生成输出文件!==='.format(self.parserRawstrList, self.parserRawstr))
                                    self.execSaveLog()
                                    CustomToast('===记录文件长度不匹配, 请检查!===\n===当前循环的记录文件长度:{}, 解析文件累计长度:{}==='.format(self.parserRawstrLen, self.accSlicedLen), timeout=5000)
                                else:
                                    self.execSaveLog()
    def execSaveLog(self):
        try:
            repeatMaxTimeList = max([len(it['rawArr']) for it in self.parserfileList])
            list_size = sys.getsizeof(self.parserRawstrList)
            self.dock_content.append('===repeatMaxTimeList_:{}, list_size_: {}==='.format(repeatMaxTimeList, list_size))
            fileName ='exportlog/outputfile/{}.csv'.format(self.loadFileName)
            with open(fileName, 'w', encoding='utf_8_sig', newline='') as f:
                f_csv = csv.writer(f)
                f_csv.writerow( [item['name'] for item in self.parserfileList if item['name']!='RESERVED'] )
            while repeatMaxTimeList>0:
                itemValList = []
                for item in self.parserfileList:
                    if item['name']=='RESERVED':
                        continue
                        #保留字站位不显示
                    citemVal = item['rawArr'].pop(0) if item['rawArr'] else ''
                    itemValList.append(citemVal)
                f_csv.writerow(itemValList)
                repeatMaxTimeList-=1
                filePathInput3.setText(fileName)
                detailList.addItem('===转换成功, 输出路径: {} success==='.format(fileName))
                detailList.item(detailList.count() -1).setForeground(QColor('green'))
                self.parserRawstrList = copy.deepcopy(self.parserRawstrListCopy)
        except Exception as e:
            logger.error('--- format_file_output_csv_ERR: {}! ---'.format(e))
            self.statusBar.showMessage('--- save format_file_output_csv_ERR: {}! ---'.format(e), 3000)
    def parserfileHandler(self, readOnceFlag=False):
        for item in self.parserfileList:
            if readOnceFlag or item['repeatFlag']:
                # U8一个字节，U16两个字节，U32四个字节
                if item['dataType']=='U8':
                    slicedLen = 1
                elif item['dataType']=='U16' or item['dataType']=='S16':
                    slicedLen = 2
                elif item['dataType']=='U32':
                    slicedLen = 4
                elif item['dataType']=='TIME':
                    slicedLen = 4
                elif item['dataType']=='FLOAT':
                    slicedLen = 4
                else:
                    slicedLen = 1
                    self.accSlicedLen += slicedLen
                    if len(self.parserRawstr)==0:
                        self.dock_content.append('===解析规则长度与记录文件长度不匹配, 请检查: {}!==='.format(self.parserRawstr))
                        self.ruleMatchedFlag = False
                        if self.parserRawstr:
                            slicedStr = self.parserRawstr[0: slicedLen]
                            # 文件数据模式【大端1或者小端0】【默认为大端模式,高位在前;小端的需要翻转一下字节顺序】
                            slicedStr = slicedStr[::-1] if self.fileDataMode==0 else slicedStr
                            if len(slicedStr)!=slicedLen:
                                self.dock_content.append('===解析规则长度与记录文件长度不匹配, 请检查:{},{},{}!==='.format(self.parserRawstr, slicedLen, slicedStr))
                                self.ruleMatchedFlag = False
                                break
                            self.parserRawstr = self.parserRawstr[slicedLen:]
                            if item['dataType']=='TIME':
                                slicedStr = TimestampToRTC(int.from_bytes(slicedStr, byteorder='big'))
                            elif item['dataType']=='FLOAT':
                                slicedStr = struct.unpack('!f', slicedStr)[0]
                                slicedStr = round(slicedStr, item['decimalPlace'])
                                # if slicedStr and item['decimalPlace']>0:
                                # slicedStr = slicedStr / pow(10, item['decimalPlace'])
                            else:
                                slicedStr = int.from_bytes(slicedStr, byteorder='big')
                                if slicedStr and item['decimalPlace']>0:
                                    slicedStr = slicedStr / pow(10, item['decimalPlace'])
                                    item['rawArr'].append(slicedStr)
    def execOpenFile(self):
        if filePathInput3.text()=='':
            return CustomToast('找不到对应文件, 请检查!')
        file_path = os.getcwd()+ '/' + filePathInput3.text()
        if platform.system() == 'Windows':
            os.startfile(file_path)
        elif platform.system() == 'Darwin':
            # macOS
            subprocess.call(('open', file_path))
        else:
            # Linux
            subprocess.call(('xdg-open', file_path))
    def sendBufferText(self, tsender='send_timer'):
        try:
            # 获取 QTextEdit 中的所有文本,# 按行分割文本
            all_text = bufferTextNode.toPlainText()
            # if not all_text: return
            if tsender=='sendBuffer_btn':
                self.bufferLines = [txt.strip() for txt in all_text.split('\n') if txt.strip()!='']
            else:
                if not self.bufferLines:
                    self.bufferLines = [txt.strip() for txt in all_text.split('\n') if txt.strip()!='']
                    if not self.bufferLines:
                        return
                    if len(self.bufferLines)>1:
                        sendIntervalTimer = int(intervalTimerNode.text()) if int(intervalTimerNode.text()) else 1000
                        self.intervalTimer.start(sendIntervalTimer)
                        self.readBytesOnlyFlag = True
                    else:
                        if not self.intervalCheckbox.isChecked():
                            self.intervalTimer.stop()
                            self.readBytesOnlyFlag = False
                            loopTxBuffer = self.bufferLines.pop(0)
                            if self.crcCheckbox.isChecked():
                                checksum = calc_crc(loopTxBuffer)
                                loopTxBuffer = '{} {} {}'.format(loopTxBuffer, checksum[0], checksum[1])
                                loopTxBuffer = loopTxBuffer.replace(' ', '')
                                binaryTxBuffer = binascii.a2b_hex(loopTxBuffer)
                                self.Com_Send_Data(binaryTxBuffer)
        except Exception as e:
            logger.error('--- binaryTxBuffer_ERR: {}! ---'.format(e))
            CustomToast('---binaryTxBuffer_ERR: {}! ---'.format(e), color='red')
    def intervalCheckboxToggled(self, state):
        if state:
            sendIntervalTimer = int(intervalTimerNode.text()) if int(intervalTimerNode.text()) else 1000
            self.intervalTimer.start(sendIntervalTimer)
            self.readBytesOnlyFlag = True
        else:
            self.intervalTimer.stop()
            self.readBytesOnlyFlag = False
    def updateReadMCUdata(self):
        # Reg32---zfill
        if self.insertReadMCUFlag=='mcuAddrValue':
            cAddr = int(self.mcuInputReg1.text().strip())
            hVal = int(self.historyResData.get(cAddr, 0))
            lVal = int(self.historyResData.get(cAddr+1, 0))
            indexValueFormat = hVal * 0x10000 + lVal
            if self.mcuDataByteList.currentText()=='大端':
                indexValueFormat = lVal * 0x10000 + hVal
                indexValueFormat = bin(indexValueFormat).replace('0b','').zfill(32)
                self.mcuInputValue1.setText(str(indexValueFormat))
            elif self.insertReadMCUFlag=='mcuDataValue':
                cAddr = int(self.mcuInputReg2.text().strip())
                hVal = int(self.historyResData.get(cAddr, 0))
                lVal = int(self.historyResData.get(cAddr+1, 0))
                indexValueFormat = hVal * 0x10000 + lVal
                if self.mcuDataByteList2.currentText()=='大端':
                    indexValueFormat = lVal * 0x10000 + hVal
                    indexValueFormat = bin(indexValueFormat).replace('0b','').zfill(32)
                    self.mcuInputValue2.setText(str(indexValueFormat))
                    self.dock_content.append('caddr_:{}, _hv_:{} | lv_:{}, indexValueFormat_:{}'.format(cAddr,hVal, lVal, indexValueFormat))
                    self.insertReadMCUFlag = False
    def mcuReadClicked1(self):
        if not self.mcuInputReg1.text().strip():
            return CustomToast('input_is_required, please_check!', color='red')
        self.readRegAddr = int(self.mcuInputReg1.text())
        self.readRegCount = 2
        self.statusBar.showMessage('=== insert_read: addr_: {}, cnt_: {} ==='.format(self.readRegAddr, self.readRegCount), 3000)
        self.edgeNumber = 5 + self.readRegCount*2
        self.insertReadFlag = True
        self.insertReadMCUFlag = 'mcuAddrValue'
        readBuffer = getreadcrc(int(self.rwStationNode.text().strip()), self.readRegAddr, self.readRegCount)
        self.delayTimer.singleShot(100,lambda: self.insertReadList(readBuffer) )
    def mcuReadClicked2(self):
        if not self.mcuInputReg2.text().strip():
            return CustomToast('input_is_required, please_check!', color='red')
        self.readRegAddr = int(self.mcuInputReg2.text())
        self.readRegCount = 2
        self.statusBar.showMessage('=== insert_read: addr_: {}, cnt_: {} ==='.format(self.readRegAddr, self.readRegCount), 3000)
        self.edgeNumber = 5 + self.readRegCount*2
        self.insertReadFlag = True
        self.insertReadMCUFlag = 'mcuDataValue'
        readBuffer = getreadcrc(int(self.rwStationNode.text().strip()), self.readRegAddr, self.readRegCount)
        self.delayTimer.singleShot(100,lambda: self.insertReadList(readBuffer) )
    def mcuWriteClicked1(self):
        self.dock_content.append('mcu_reg_:{}, val_:{}'.format(self.mcuInputReg1.text(), self.mcuInputValue1.text() ))
        if not self.mcuInputReg1.text().strip() or not self.mcuInputValue1.text().strip():
            return CustomToast('inputValue_is_required, please_check!')
        if True:
            # return self.showMessage( '请输入二进制的地址值!')
            return CustomToast('binary_inputVal_is_required, please_check!')
    def mcuWriteClicked2(self):
        self.dock_content.append('mcuDataTypeList_: {}'.format(self.mcuDataTypeList.currentText()))
        # Reg32
    def mcuDataByteListChanged(self, val):
        self.dock_content.append('byteval_:{}'.format(val))
    def mcuDataByteListChanged2(self, val):
        self.dock_content.append('byteval2_:{}'.format(val))
    def mcuDataTypeListChanged(self, val):
        self.dock_content.append('type_val_:{}'.format(val))
    def onHelpAbout(self):
        if not os.path.exists('./config/userHelp.txt'):
            return QMessageBox.critical(self, 'ErrorMsg', 'missing_file[userHelp.txt], please_check!')
        try:
            with open ('./config/userHelp.txt', 'r', encoding='utf8') as f:
                content = f.read()
            UserHelpDialog = QDialog(self)
            UserHelpDialog.setWindowTitle('用户操作指南')
            UserHelpDialog.setWindowIcon(QIcon('./icons/help.png'))
            UserHelpDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
            UserHelpDialog.finished.connect(self.recordDialogFinished)
            UserHelpDialog.resize(900, 600)
            userHelpText = QTextEdit(self)
            userHelpText.setReadOnly(True)
            # 设置为只读
            userHelpText.setText(content)
            userHelpText.setLineWrapMode(QTextEdit.WidgetWidth)
            # 设置自动换行
            # 设置首行缩进&行间距
            cursor = userHelpText.textCursor()
            blockFormat = QTextBlockFormat()
            blockFormat.setLineHeight(24, QTextBlockFormat.FixedHeight)
            # 设置行间距为 24 像素
            blockFormat.setTextIndent(26)
            # 缩进26像素
            cursor.select(QTextCursor.Document)
            cursor.mergeBlockFormat(blockFormat)
            contentListLayout = QHBoxLayout()
            contentListLayout.addWidget(userHelpText)
            UserHelpDialog.setLayout(contentListLayout)
            UserHelpDialog.show()
            UserHelpDialog.move(self.geometry().left(), self.geometry().top())
            # 设置对话框的位置
        except Exception as e:
            logger.error('---read_user_help.txt_err: {}!---'.format(e))
            QMessageBox.critical(self, 'ErrorMsg', '---err: {}!---'.format(e))
if __name__ == '__main__':
    # 打包的时候记得把这一段放开，设置任务栏的图标样式
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("v20250110")
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    # app.setStyle(QStyleFactory.create("windowsvista"))
    # # ['windowsvista', 'Windows', 'Fusion'] #三种风格的界面
    window1 = MultiTabMonitor()
    window1.show()
    # 创建系统托盘图标
    tray_icon = QSystemTrayIcon( QIcon('./icons/monitor.png'), app)
    # 创建托盘菜单
    menu = QMenu()
    menu.addAction( QAction(QIcon('./icons/close.png'),'退出', menu, triggered=window1.close) )
    tray_icon.setContextMenu(menu)
    # 显示任务栏图标
    tray_icon.show()
    tray_icon.activated.connect(window1.showNormal)
    # 新创建一个弹框和他的控件布局以及方法
    bufferDialog = QDialog(window1)
    bufferDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    bufferDialog.setWindowTitle(window1.langData.get('buffer_dialog'))
    bufferDialog.setWindowIcon( QIcon('./icons/connect_device.png'))
    bufferDialog.finished.connect(window1.bufferDialogFinished)
    bufferDialog.resize(700, 400)
    appendLineBox = QHBoxLayout()
    bufferTextNode = QTextEdit('')
    # 设置 QTextEdit 的宽度和高度
    bufferTextNode.setFixedSize(300, 50)
    bufferTextNode.setFixedHeight(50)
    appendLineBox.addWidget(bufferTextNode, alignment=Qt.AlignBottom)
    appendSendBtn = QPushButton(window1.langData.get('send_btn'), clicked=lambda:window1.sendBufferText('sendBuffer_btn'))
    appendSendBtn.setFocusPolicy(Qt.NoFocus)
    appendSendBtn.setFixedWidth(60)
    appendLineBox.addWidget(appendSendBtn, alignment=Qt.AlignBottom)
    window1.intervalCheckbox = QCheckBox(window1.langData.get('send_interval'))
    window1.intervalCheckbox.toggled.connect(window1.intervalCheckboxToggled)
    appendLineBox.addWidget(window1.intervalCheckbox, alignment=Qt.AlignBottom)
    intervalTimerNode = QLineEdit('1000')
    intervalTimerNode.setFixedWidth(40)
    intervalTimerNode.setValidator(intPositiveValidator)
    appendLineBox.addWidget(intervalTimerNode, alignment=Qt.AlignBottom)
    window1.crcCheckbox = QCheckBox('ModbusCRC16')
    appendLineBox.addWidget(window1.crcCheckbox, alignment=Qt.AlignBottom)
    firstLineBox = QHBoxLayout()
    bufferDialogVbox = QVBoxLayout()
    bufferDialog.setLayout(bufferDialogVbox)
    # 开始添加控件, # 左边第一列
    sendLabel = QLabel(window1.langData.get('send_count')+':')
    receiveLabel = QLabel(window1.langData.get('receive_count')+':')
    # sendLabel.setStyleSheet('max-width:30px;')
    # receiveLabel.setStyleSheet('max-width:30px;')
    window1.label_txt = QLabel("0")
    window1.label_rxt = QLabel("0")
    window1.label_txt.setFixedWidth(70)
    window1.label_rxt.setFixedWidth(70)
    firstLineBox.addWidget(sendLabel)
    firstLineBox.addWidget(window1.label_txt)
    firstLineBox.addWidget(receiveLabel)
    firstLineBox.addWidget(window1.label_rxt)
    window1.receiveHexNode = QCheckBox('HEX')
    window1.receiveHexNode.setChecked(True if window1.configSettingMap.get('receiveHexFlag','')=='True' else False)
    firstLineBox.addWidget(window1.receiveHexNode)
    window1.toggle_text = QCheckBox(window1.langData.get('update_buffer'))
    firstLineBox.addWidget(window1.toggle_text)
    saveTxtBtn = QPushButton(window1.langData.get('save_buffer'), clicked=window1.saveListItem)
    clearBtn = QPushButton(window1.langData.get('clear_buffer'), clicked=window1.DeleteListItem)
    firstLineBox.addWidget(saveTxtBtn)
    firstLineBox.addWidget(clearBtn)
    window1.searchTextBox = QLineEdit()
    # 设置占位文本
    window1.searchTextBox.setPlaceholderText(window1.langData.get('input_search_buffer'))
    firstLineBox.addWidget(window1.searchTextBox)
    searchTextBtn = QPushButton(window1.langData.get('search_buffer'), clicked=window1.keyupSearchText)
    firstLineBox.addWidget(searchTextBtn)
    set_all_buttons_noFocus(firstLineBox)
    # 添加最右边的列表区域,用于打印信息
    window1.rightList = CustomTextEdit(window1)
    bufferDialogVbox.addWidget(window1.rightList)
    bufferDialogVbox.addLayout(firstLineBox)
    bufferDialogVbox.addLayout(appendLineBox)
    # 新创建一个log的弹框
    faultLogDialog = QDialog(window1)
    faultLogDialog.setWindowTitle(window1.langData.get('file_upload'))
    faultLogDialog.setWindowIcon( QIcon('./icons/transfer2.png'))
    faultLogDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    faultLogDialog.finished.connect(window1.faultLogDialogFinished)
    faultLogDialog.resize(1000, 500)
    # 日志区域&故障区域的节点组件
    logBox1 = QHBoxLayout()
    readWriteReg = QLineEdit('')
    readIndexRangeInput = QLineEdit('1-9999')
    readIndexRangeInput.setInputMask('0000-0000')
    readWriteReg.setFixedWidth(60)
    readIndexRangeInput.setFixedWidth(60)
    logBox1.addWidget(QLabel('事件点位'))
    logBox1.addWidget(readWriteReg)
    logBox1.addWidget(QLabel('索引范围'))
    logBox1.addWidget(readIndexRangeInput)
    downloadLogBtn = QPushButton('日志下载', clicked=window1.downloadLogEvent)
    downloadLogBtn.setFocusPolicy(Qt.NoFocus)
    logBox1.addWidget(downloadLogBtn)
    logBox1.addStretch(1)
    # log_zone1
    logHeaderBox1 = QHBoxLayout()
    logSlaveAddrLabel = QLabel(window1.langData.get('station_address'))
    logHeaderBox1.addWidget(logSlaveAddrLabel)
    logIDInputNode = QLineEdit(window1.configSettingMap.get('logSlaveAddr', '1'))
    logIDInputNode.setFixedWidth(60)
    logIDInputNode.setValidator(slaveAddrValidator)
    logHeaderBox1.addWidget(logIDInputNode)
    unitPackageLenNode = QLineEdit('1024')
    unitPackageLenNode.setValidator(intPositiveValidator)
    unitPackageLenNode.setFixedWidth(60)
    unitPackageLenLabel = QLabel(window1.langData.get('unit_packageLen'))
    logHeaderBox1.addWidget(unitPackageLenLabel)
    logHeaderBox1.addWidget(unitPackageLenNode)
    recordCountLabel = QLabel('{}:0'.format(window1.langData.get('record_count')))
    logHeaderBox1.addWidget(recordCountLabel)
    logHeaderBox1.addStretch(1)
    filterSearchBtn1 = QPushButton(window1.langData.get('file_refresh'), clicked=window1.filterSearchAllLog)
    filterSearchBtn1.setFixedWidth(60)
    filterSearchBtn1.setFocusPolicy(Qt.NoFocus)
    logHeaderBox1.addWidget(filterSearchBtn1)
    # 开始文件表格的节点部分
    logTableList = QTableWidget()
    logTableList.setColumnCount(6)
    logTableList.setFixedSize(580, 450)
    logTableList.setFixedHeight(300)
    logTableList.setHorizontalHeaderLabels([window1.langData.get('file_name'), window1.langData.get('file_record'), window1.langData.get('file_record_len'), window1.langData.get('file_starttime'), window1.langData.get('file_endtime'), window1.langData.get('file_operation_col')])
    # logTableList.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    logTableList.verticalHeader().setDefaultSectionSize(20)
    logTableList.setColumnWidth(0, 120)
    logTableList.setColumnWidth(1, 60)
    logTableList.setColumnWidth(2, 60)
    logTableList.setColumnWidth(3, 125)
    logTableList.setColumnWidth(4, 125)
    logTableList.setColumnWidth(5, 70)
    logTableList.setSelectionBehavior(QAbstractItemView.SelectRows)
    #设置表格的选取方式是行选取
    logTableList.setSelectionMode(QAbstractItemView.SingleSelection)
    #设置选取方式为单个选取
    # 连接单击信号到槽函数
    logTableList.cellClicked.connect(window1.onLogCellClicked)
    logTableList.verticalHeader().sectionClicked.connect(window1.handleHeaderClicked)
    window1.initSearchAllLog()
    logVbox1 = QVBoxLayout()
    # logVbox1.addLayout(logBox1)
    logVbox1.addLayout(logHeaderBox1)
    logVbox1.addWidget(logTableList)
    # 右边区域
    fileDetailBox1 = QGroupBox(window1.langData.get('file_detail'))
    logHeaderBox2 = QGridLayout()
    fileDetailBox1.setLayout(logHeaderBox2)
    filterNameNode = QLineEdit('')
    filterNameNode.setReadOnly(True)
    filterNameNode.setFixedWidth(160)
    logDetailFileLabel = QLabel(window1.langData.get('file_name'))
    logHeaderBox2.addWidget(logDetailFileLabel,0,0)
    logHeaderBox2.addWidget(filterNameNode,0,1)
    filterdownloadBtn = QPushButton(window1.langData.get('file_read'), clicked=window1.startFilterUpload)
    filterdownloadBtn.setFocusPolicy(Qt.NoFocus)
    logHeaderBox2.addWidget(filterdownloadBtn,0,2)
    filterStopBtn = QPushButton(window1.langData.get('file_read_stop'), clicked=window1.stopFileUpload)
    filterStopBtn.setFocusPolicy(Qt.NoFocus)
    filterStopBtn.setStyleSheet('color:red;')
    logHeaderBox2.addWidget(filterStopBtn,0,3)
    filterTime1Node = QDateTimeEdit()
    filterTime1Node.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    # 启用日历弹出窗口
    filterTime1Node.setCalendarPopup(True)
    filterTime1Node.setFixedWidth(160)
    filterTime1Label = QLabel(window1.langData.get('file_starttime'))
    logHeaderBox2.addWidget(filterTime1Label,1,0)
    logHeaderBox2.addWidget(filterTime1Node,1,1)
    filterTime2Node = QDateTimeEdit()
    filterTime2Node.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    filterTime2Node.setCalendarPopup(True)
    filterTime2Node.setFixedWidth(160)
    filterTime2Label = QLabel(window1.langData.get('file_endtime'))
    logHeaderBox2.addWidget(filterTime2Label,2,0)
    logHeaderBox2.addWidget(filterTime2Node,2,1)
    logVbox2 = QVBoxLayout()
    detailList = QListWidget()
    logVbox2.addWidget(fileDetailBox1)
    window1.progressbar03 = QProgressBar(window1,minimum=0, maximum=100, objectName="progressbar03")
    window1.progressbar03.setMinimum(0)
    window1.progressbar03.setMaximum(100)
    window1.progressbar03.setFixedWidth(160)
    window1.progressbar03.setValue(window1.progressbar03.minimum())
    fileProgressLabel = QLabel(window1.langData.get('file_progress'))
    logHeaderBox2.addWidget(fileProgressLabel,3,0)
    logHeaderBox2.addWidget(window1.progressbar03,3,1)
    filePackageIdxLabel = QLabel('{}:{}'.format(window1.langData.get('file_package_idx'), 0))
    logHeaderBox2.addWidget(filePackageIdxLabel,3,2)
    # logHeaderBox2.setRowStretch(logHeaderBox2.rowCount(), 1)
    # 新增导入文件的节点【包括路径输入和导入的按钮】
    fileOperation1 = QGroupBox(window1.langData.get('file_operation'))
    fileOperationvBox = QVBoxLayout()
    fileOperation1.setLayout(fileOperationvBox)
    fileOperationBox1 = QHBoxLayout()
    fileOperationvBox.addLayout(fileOperationBox1)
    filePath1Label = QLabel(window1.langData.get('log_file_path'))
    fileOperationBox1.addWidget(filePath1Label)
    filePathInput1 = QLineEdit('')
    filePathInput1.setReadOnly(True)
    filePathBtn1 = QPushButton(window1.langData.get('import_logfile'), clicked=window1.loadParseLog)
    filePathBtn1.setFocusPolicy(Qt.NoFocus)
    fileOperationBox1.addWidget(filePathInput1)
    fileOperationBox1.addWidget(filePathBtn1)
    fileOperationBox1.addStretch(1)
    fileOperationBox2 = QHBoxLayout()
    fileOperationvBox.addLayout(fileOperationBox2)
    filePath2Label = QLabel(window1.langData.get('parser_file_path'))
    fileOperationBox2.addWidget(filePath2Label)
    filePathInput2 = QLineEdit('')
    filePathInput2.setReadOnly(True)
    filePathBtn2 = QPushButton(window1.langData.get('import_parser'), clicked=window1.manualLoadParseFile)
    filePathBtn2.setFocusPolicy(Qt.NoFocus)
    fileOperationBox2.addWidget(filePathInput2)
    fileOperationBox2.addWidget(filePathBtn2)
    fileOperationBox3 = QHBoxLayout()
    fileOperationvBox.addLayout(fileOperationBox3)
    filePath3Label = QLabel(window1.langData.get('output_file_path'))
    fileOperationBox3.addWidget(filePath3Label)
    filePathInput3 = QLineEdit('')
    filePathInput3.setReadOnly(True)
    fileOperationBox3.addWidget(filePathInput3)
    openFile_dir_btn = QPushButton(window1.langData.get('open_directory'), clicked=window1.openFileLogDir)
    openFile_dir_btn.setFocusPolicy(Qt.NoFocus)
    fileOperationBox3.addWidget(openFile_dir_btn)
    fileOperationBox4 = QHBoxLayout()
    fileOperationvBox.addLayout(fileOperationBox4)
    filePathBtn3 = QPushButton(window1.langData.get('file_transform'), clicked=window1.parseAndSaveLog)
    filePathBtn3.setFocusPolicy(Qt.NoFocus)
    fileOperationBox4.addStretch(1)
    fileOperationBox4.addWidget(filePathBtn3)
    filePathBtn4 = QPushButton(window1.langData.get('open_csvfile'), clicked=window1.execOpenFile)
    filePathBtn4.setFocusPolicy(Qt.NoFocus)
    fileOperationBox4.addWidget(filePathBtn4)
    clearLogBtn = QPushButton(window1.langData.get('file_log_clear'), clicked=lambda: detailList.clear())
    clearLogBtn.setFocusPolicy(Qt.NoFocus)
    fileOperationBox4.addWidget(clearLogBtn)
    logVbox2.addWidget(fileOperation1)
    logVbox2.addWidget(detailList)
    faultLogBox = QHBoxLayout()
    faultLogBox.addLayout(logVbox1)
    faultLogBox.addLayout(logVbox2)
    faultLogDialog.setLayout(faultLogBox)
    # 新创建一个数据读写的弹框
    dataRWDialog = QDialog(window1)
    dataRWDialog.setWindowIcon( QIcon('./icons/setting2.png'))
    dataRWDialog.setWindowTitle(window1.langData.get('data_read_write'))
    dataRWDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    dataRWDialog.finished.connect(window1.recordDialogFinished)
    dataRWDialog.resize(700, 400)
    # 新创建一个导入导出的弹框
    mcuGbox1 = QGroupBox(window1.langData.get('mcu_addr_setting'))
    mcuHbox1 = QHBoxLayout()
    mcuGbox1.setLayout(mcuHbox1)
    mcuGbox1.setEnabled(False)
    mcuLabel1 = QLabel(window1.langData.get('register_name'))
    mcuLabel2 = QLabel(window1.langData.get('register_addr'))
    mcuBtn1 = QPushButton(window1.langData.get('read_btn'), clicked=window1.mcuReadClicked1)
    mcuBtn2 = QPushButton(window1.langData.get('write_btn'), clicked=window1.mcuWriteClicked1)
    window1.mcuInputReg1 = QLineEdit('')
    window1.mcuInputValue1 = QLineEdit('')
    window1.mcuInputReg1.setFixedWidth(80)
    window1.mcuInputValue1.setFixedWidth(160)
    window1.mcuDataByteList = QComboBox()
    window1.mcuDataByteList.addItems(['小端', '大端'])
    window1.mcuDataByteList.activated[str].connect(window1.mcuDataByteListChanged)
    window1.mcuDataByteList.setFixedWidth(80)
    mcuHbox1.addWidget(mcuLabel1)
    mcuHbox1.addWidget(window1.mcuInputReg1)
    mcuHbox1.addWidget(mcuLabel2)
    mcuHbox1.addWidget(window1.mcuInputValue1)
    mcuHbox1.addWidget(window1.mcuDataByteList)
    mcuHbox1.addStretch(1)
    mcuHbox1.addWidget(mcuBtn1)
    mcuHbox1.addWidget(mcuBtn2)
    set_all_buttons_noFocus(mcuHbox1)
    # 【mcu】第二部分的地址数据
    mcuGbox2 = QGroupBox(window1.langData.get('mcu_addr_value'))
    mcuHbox2 = QHBoxLayout()
    mcuGbox2.setLayout(mcuHbox2)
    mcuGbox2.setEnabled(False)
    mcuLabel2_1 = QLabel(window1.langData.get('register_name'))
    mcuLabel3 = QLabel(window1.langData.get('register_value'))
    mcuLabel4 = QLabel(window1.langData.get('data_type'))
    mcuBtn3 = QPushButton(window1.langData.get('read_btn'), clicked=window1.mcuReadClicked2)
    mcuBtn4 = QPushButton(window1.langData.get('write_btn'), clicked=window1.mcuWriteClicked2)
    window1.mcuInputReg2 = QLineEdit('')
    window1.mcuInputValue2 = QLineEdit('')
    window1.mcuInputReg2.setFixedWidth(80)
    window1.mcuInputValue2.setFixedWidth(160)
    window1.mcuDataByteList2 = QComboBox()
    window1.mcuDataByteList2.addItems(['小端', '大端'])
    window1.mcuDataByteList2.activated[str].connect(window1.mcuDataByteListChanged2)
    window1.mcuDataByteList2.setFixedWidth(80)
    window1.mcuDataTypeList = QComboBox()
    window1.mcuDataTypeList.addItems(['Float', 'Int32', 'UInt32', 'Int16', 'UInt16', 'Int8', 'UInt8', ])
    window1.mcuDataTypeList.activated[str].connect(window1.mcuDataTypeListChanged)
    window1.mcuDataTypeList.setFixedWidth(80)
    window1.mcuDataTypeList.setCurrentText('Int32')
    # window1.mcuDataTypeList.setDisabled(True)
    mcuHbox2.addWidget(mcuLabel2_1)
    mcuHbox2.addWidget(window1.mcuInputReg2)
    mcuHbox2.addWidget(mcuLabel3)
    mcuHbox2.addWidget(window1.mcuInputValue2)
    mcuHbox2.addWidget(window1.mcuDataByteList2)
    mcuHbox2.addWidget(mcuLabel4)
    mcuHbox2.addWidget(window1.mcuDataTypeList)
    mcuHbox2.addStretch(1)
    mcuHbox2.addWidget(mcuBtn3)
    mcuHbox2.addWidget(mcuBtn4)
    set_all_buttons_noFocus(mcuHbox2)
    # 最后一个tab,添加数据读写模块
    window1.rwStationNode = QLineEdit(window1.configSettingMap.get('rwSlaveAddr', '1'))
    window1.rwStationNode.setValidator(slaveAddrValidator)
    window1.startAddrNode = QLineEdit(window1.configSettingMap.get('rwStartAddr', '2000'))
    window1.startAddrNode.setValidator(int0_65535Validator)
    window1.startAddrNode.textChanged.connect(window1.onstartAddrChanged)
    window1.rwStationNode.setFixedWidth(80)
    window1.startAddrNode.setFixedWidth(80)
    # 加入一个输入框防抖的延时器
    window1.debounceTimer = QTimer(window1)
    window1.debounceTimer.timeout.connect(window1.initStartAddrText)
    window1.startAddrNode.editingFinished.connect(window1.startAddrEdited)
    window1.startCountNode = QComboBox()
    window1.startCountNode.setFixedWidth(80)
    for cnt in range(1,65):
        window1.startCountNode.addItem(str(cnt))
        window1.startCountNode.activated[str].connect(window1.startCountChanged)
    window1.readBtnNode = QPushButton(window1.langData.get('read_btn'), clicked=window1.readBtnClicked)
    window1.writeBtnNode = QPushButton(window1.langData.get('write_btn'), clicked=window1.writeBtnClicked)
    # 添加节点到第一行
    window1.stationLabel = QLabel(window1.langData.get('station_address'))
    window1.stationLabel.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
    rwHeaderLine = QHBoxLayout()
    rwHeaderLine.addWidget(window1.stationLabel)
    rwHeaderLine.addWidget(window1.rwStationNode)
    window1.addrLabel = QLabel(window1.langData.get('register_address'))
    window1.addrLabel.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
    rwHeaderLine.addWidget(window1.addrLabel)
    rwHeaderLine.addWidget(window1.startAddrNode)
    window1.rwHexNode = QCheckBox('HEX')
    window1.rwHexNode.toggled.connect(window1.toggle_hexBox)
    rwHeaderLine.addWidget(window1.rwHexNode)
    window1.countLabel = QLabel(window1.langData.get('register_count'))
    window1.countLabel.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
    rwHeaderLine.addWidget(window1.countLabel)
    rwHeaderLine.addWidget(window1.startCountNode)
    rwHeaderLine.addWidget(window1.readBtnNode)
    rwHeaderLine.addWidget(window1.writeBtnNode)
    # rwHeaderLine.addWidget(QLabel(''))
    rwHeaderLine.addStretch(1)
    set_all_buttons_noFocus(rwHeaderLine)
    # 把第一行的头布局加入的组件中
    headerWidget = QWidget()
    headerWidget.setLayout(rwHeaderLine)
    window1.readWriteGrid = QGridLayout()
    window1.read_write_box = QGroupBox(window1.langData.get('read_write_tips'))
    window1.read_write_box.setLayout(window1.readWriteGrid)
    window1.startCountChanged()
    # 初始化数读写模块的节点
    vbox = QVBoxLayout()
    vbox.addWidget(mcuGbox1)
    vbox.addWidget(mcuGbox2)
    # 创建一个水平的分隔线
    hLine = QFrame()
    hLine.setFrameShape(QFrame.HLine)
    hLine.setFrameShadow(QFrame.Sunken)
    vbox.addWidget(hLine)
    vbox.addWidget(headerWidget)
    vbox.addWidget(window1.read_write_box)
    vbox.addStretch(1)
    dataRWDialog.setLayout(vbox)
    # 波形展示和软件示波器共有一个的弹框界面
    plotWidDialog = childFollowMoveDialog(window1)
    plotWidDialog.setWindowIcon( QIcon('./icons/datawave.png'))
    plotWidDialog.setWindowTitle(window1.langData.get('plot_tab_name'))
    plotWidDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    plotWidDialog.resize(1200, 800)
    # 添加波形展示tab页 # 设置 QIntValidator，范围为 1 到 255
    headerLine1 = QHBoxLayout()
    window1.salveAddressNode = QLineEdit(window1.configSettingMap.get('modeSlaveAddr', '1'))
    window1.salveAddressNode.setValidator(slaveAddrValidator)
    window1.salveAddressNode.setFixedWidth(40)
    slaveAddrLabel = QLabel(window1.langData.get('station_address'))
    headerLine1.addWidget(slaveAddrLabel)
    headerLine1.addWidget(window1.salveAddressNode)
    window1.togglePlotBtn = QPushButton(window1.langData.get('start_display'), clicked=window1.toggle_plotGraph)
    window1.togglePlotBtn.setStyleSheet('background:green')
    headerLine1.addWidget(window1.togglePlotBtn) # 添加设置通道按钮
    window1.settingBtn = QPushButton(window1.langData.get('set_channel'), clicked=window1.setChannelCFG)
    headerLine1.addWidget(window1.settingBtn)
    window1.saveDataNode = QPushButton(window1.langData.get('save_data_btn'), clicked=window1.exportSoftwaveDataCSV)
    headerLine1.addWidget(window1.saveDataNode)
    window1.openDataNode = QPushButton(window1.langData.get('open_history_data'), clicked=window1.openSoftWavefile)
    headerLine1.addWidget(window1.openDataNode)
    window1.clearDataNode = QPushButton(window1.langData.get('clear_cache_data'), clicked=window1.clearCachedGrid)
    headerLine1.addWidget(window1.clearDataNode)
    window1.resetNode = QPushButton(window1.langData.get('refresh_plot'))
    window1.resetNode.clicked.connect(window1.resetWaveChart)
    headerLine1.addWidget(window1.resetNode)
    window1.toggleCursorBtn = QCheckBox(window1.langData.get('plot_tip'))
    window1.toggleCursorBtn.toggled.connect(window1.toggle_Cursor)
    headerLine1.addWidget(window1.toggleCursorBtn)
    window1.chk_cursor = QCheckBox(window1.langData.get('vernier_caliper'))
    window1.chk_cursor.toggled.connect(window1.switchCursor)
    headerLine1.addWidget(window1.chk_cursor)
    # 设置按钮节点不要默认聚焦
    window1.startButtonNode = QPushButton(window1.langData.get('start_monitoring'), clicked=window1.execStartResult)
    window1.startButtonNode.setStyleSheet('background:green')
    headerLine1.addWidget(window1.startButtonNode)
    window1.stopButtonNode = QPushButton(window1.langData.get('stop_monitoring'), clicked=window1.execStopResult)
    window1.stopButtonNode.setStyleSheet('background:red')
    headerLine1.addWidget(window1.stopButtonNode)
    headerLine1.addStretch(1)
    set_all_buttons_noFocus(headerLine1)
    headerLine1.setContentsMargins(5,5,0,0)
    # add_second_line
    headerLine2 = QHBoxLayout()
    line2Label1 = QLabel(window1.langData.get('mode_setting'))
    line2Label1.setFixedHeight(20)
    headerLine2.addWidget(line2Label1)
    window1.modeTypeList=QComboBox()
    window1.modeTypeList.addItems(['在线模式','离线模式'])
    window1.modeTypeList.activated[str].connect(window1.selectModeType)
    window1.modeTypeList.setCurrentIndex(int(window1.configSettingMap.get('waveModetype', '0')))
    headerLine2.addWidget(window1.modeTypeList)
    line2Label2 = QLabel(window1.langData.get('data_source'))
    line2Label2.setFixedHeight(20)
    headerLine2.addWidget(line2Label2)
    window1.dataTypeList=QComboBox()
    window1.dataTypeList.addItems(['通道选择','地址设置'])
    window1.dataTypeList.activated[str].connect(window1.selectDataType)
    window1.dataTypeList.setCurrentIndex(int(window1.configSettingMap.get('waveDatatype', '0')))
    headerLine2.addWidget(window1.dataTypeList) # 默认隐藏触发模式,相关节点切换以后才会显示界面上
    window1.multiSelect = ComboCheckBox(window1.regNameList)
    window1.multiSelect.setStyleSheet('width:100px;')
    if len(window1.checkedChannelList)>0:
        window1.multiSelect.set_selected(window1.checkedChannelList)
        window1.multiSelect.text.setText(','.join(window1.checkedChannelList))
        window1.multiSelect.myCheckBoxClickSig.connect(window1.getCheckedList)
    headerLine2.addWidget(window1.multiSelect)
    window1.setAddressBtn = QPushButton(window1.langData.get('set_address'), clicked=window1.setChannelAddress)
    headerLine2.addWidget(window1.setAddressBtn)
    window1.setAddressBtn.hide()
    window1.triggerlabel = QLabel(window1.langData.get('trigger_mode'))
    window1.triggerlabel.setFixedHeight(20)
    headerLine2.addWidget(window1.triggerlabel)
    window1.triggerTypeList=QComboBox()
    window1.triggerTypeList.addItems(['手动','上升沿','下降沿','上升下降双向触发'])
    window1.triggerTypeList.setCurrentIndex(int(window1.configSettingMap.get('waveTriggertype', '0')))
    window1.triggerTypeList.insertSeparator(1)
    window1.triggerTypeList.activated[str].connect(window1.selectTriggerType)
    headerLine2.addWidget(window1.triggerTypeList)
    window1.triggerlabel.hide()
    window1.triggerTypeList.hide()
    # 默认隐藏触发条件,相关节点切换以后才会显示界面上
    window1.triggerManualBtn = QPushButton(window1.langData.get('manual_trigger'), clicked=window1.triggerManualBtnClicked)
    headerLine2.addWidget(window1.triggerManualBtn)
    window1.triggerManualBtn.hide()
    window1.triggerlabel2 = QLabel(window1.langData.get('trigger_channel'))
    window1.triggerlabel2.setFixedHeight(20)
    headerLine2.addWidget(window1.triggerlabel2)
    window1.triggerChannelList=QComboBox()
    window1.triggerChannelList.activated[str].connect(window1.selectTriggerChannel)
    headerLine2.addWidget(window1.triggerChannelList)
    window1.triggerlabel3 = QLabel(window1.langData.get('trigger_value'))
    window1.triggerlabel3.setFixedHeight(20)
    headerLine2.addWidget(window1.triggerlabel3)
    window1.triggerInput = QLineEdit()
    window1.triggerInput.setValidator(QRegExpValidator(QRegExp("^[A-Fa-f0-9]{4}$")))
    window1.triggerInput.setFixedWidth(50)
    headerLine2.addWidget(window1.triggerInput)
    window1.triggerlabel2.hide()
    window1.triggerChannelList.hide()
    window1.triggerlabel3.hide()
    window1.triggerInput.hide()
    # 添加计数显示和统计
    headerLine2.addStretch(1)
    window1.samplePeriodNode = QLineEdit(window1.configSettingMap.get('modeSamplePeriod', '2'))
    window1.samplePeriodNode.setFixedWidth(40)
    window1.samplePeriodNode.setValidator(intPositiveValidator)
    # window1.samplePeriodNode.setRange(1,99)
    refreshLabel = QLabel(window1.langData.get('sample_circle'))
    headerLine2.addWidget(refreshLabel)
    headerLine2.addWidget(window1.samplePeriodNode)
    window1.sampleCountNode = QLineEdit(window1.configSettingMap.get('modeSampleIndex', '3'))
    window1.sampleCountNode.setFixedWidth(40)
    window1.sampleCountNode.setValidator(intPositiveValidator)
    sampleLabel = QLabel(window1.langData.get('sample_count_time'))
    headerLine2.addWidget(sampleLabel)
    headerLine2.addWidget(window1.sampleCountNode)
    sampleLabel.hide()
    window1.sampleCountNode.hide()
    cacheLenLabel = QLabel(window1.langData.get('cache_length'))
    headerLine2.addWidget(cacheLenLabel)
    window1.cacheLengthNode = QLineEdit(window1.configSettingMap.get('cacheLength', '500'))
    window1.cacheLengthNode.setValidator(intPositiveValidator)
    window1.cacheLengthNode.editingFinished.connect(window1.cacheLenRefresh)
    window1.cacheLengthNode.setFixedWidth(70)
    headerLine2.addWidget(window1.cacheLengthNode)
    window1.waveprogressbar = QProgressBar(window1, minimum=0, maximum=2,textVisible=False, objectName="waveprogressbar01")
    window1.waveprogressbar.setFixedSize(50, 16)
    headerLine2.addWidget(window1.waveprogressbar)
    window1.wavelabel_rxt = QLabel('{}: 0'.format(window1.langData.get('channel_data_counts')))
    window1.wavelabel_rxt.setFixedSize(150,20)
    headerLine2.addWidget(window1.wavelabel_rxt)
    headerLine2.setContentsMargins(5,5,0,0)
    set_all_buttons_noFocus(headerLine2)
    headerLine3 = QHBoxLayout()
    setPlotBackgroundNode = QComboBox()
    setPlotBackgroundNode.addItem(window1.langData.get('set_canvas_bg_color'))
    setPlotBackgroundNode.addItem('白色', 'w')
    setPlotBackgroundNode.addItem('黑色', 'k')
    setPlotBackgroundNode.activated[str].connect(window1.setPlotBackground)
    # 禁用默认值的选择
    setPlotBackgroundNode.model().item(0).setEnabled(False)
    headerLine3.addWidget(setPlotBackgroundNode)
    clear_graph_outputNode = QPushButton(window1.langData.get('clear_display'), clicked=window1.clear_graph_output)
    headerLine3.addWidget(clear_graph_outputNode)
    saveImg_Button_Node = QPushButton(window1.langData.get('save_as_image'), clicked=window1.saveImg_Button_clicked)
    headerLine3.addWidget(saveImg_Button_Node)
    chk_gridmode = QCheckBox(window1.langData.get('set_grid_line'))
    chk_gridmode.setChecked(True)
    chk_gridmode.toggled.connect(window1.resetChartGrid)
    headerLine3.addWidget(chk_gridmode)
    chk_mousemode = QCheckBox(window1.langData.get('set_mouse_mode'))
    chk_mousemode.toggled.connect(window1.resetMouseMode)
    headerLine3.addWidget(chk_mousemode)
    chk_mouseXEnable = QCheckBox(window1.langData.get('set_mouseX_enable'))
    chk_mouseXEnable.toggled.connect(window1.set_mouseXEnable)
    headerLine3.addWidget(chk_mouseXEnable)
    chk_mouseYEnable = QCheckBox(window1.langData.get('set_mouseY_enable'))
    chk_mouseYEnable.toggled.connect(window1.set_mouseYEnable)
    headerLine3.addWidget(chk_mouseYEnable)
    # headerLine3.addStretch(1)
    headerLine3.setContentsMargins(5,5,0,0)
    set_all_buttons_noFocus(headerLine3)
    # 设置画图部分 #调试方便临时注释
    window1.initPlotGraph()
    #初始化图形界面 # 设置全局的布局
    lastvlayout = QVBoxLayout()
    lastvlayout.addLayout(headerLine1)
    headerLine2Wrapper = QWidget()
    headerLine2Wrapper.setFixedHeight(30)
    headerLine2Wrapper.setLayout(headerLine2)
    lastvlayout.addLayout(headerLine3)
    lastvlayout.addWidget(headerLine2Wrapper)
    # lastvlayout.addLayout(headerLine2)
    lastvlayout.addWidget(window1.graph_win)
    #调试方便临时注释 # lastvlayout.addStretch(1)
    lastvlayout.setContentsMargins(5, 5, 5, 5)
    plotWidDialog.setLayout(lastvlayout)
    # 实时数据的波形展示的弹框界面
    plotMonitorDialog = QDialog(window1)
    plotMonitorDialog.setWindowIcon( QIcon('./icons/datawave.png'))
    plotMonitorDialog.setWindowTitle(window1.langData.get('plot_realTime_data'))
    plotMonitorDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    plotMonitorDialog.resize(1200, 800)
    plotMonitorDialog.finished.connect(window1.plotMonitorDialogFinished) #关闭对话框并发出finished信号
    plotheaderLine1 = QHBoxLayout()
    window1.openSelectBtn = QPushButton(window1.langData.get('select_channel'))
    window1.openSelectBtn.clicked.connect(window1.openChannelDialog)
    plotheaderLine1.addWidget(window1.openSelectBtn)
    window1.togglePlotBtn2 = QPushButton(window1.langData.get('start_display'), clicked=window1.toggle_plotMonitorGraph)
    window1.togglePlotBtn2.setStyleSheet('background:green')
    plotheaderLine1.addWidget(window1.togglePlotBtn2)
    # 添加设置通道宽度的输入框
    window1.screenWLabel = QLabel(window1.langData.get('screen_width'))
    window1.screenWLabel.setFixedWidth(80)
    window1.screenWLabel.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
    window1.screenWidthNode = QLineEdit(window1.configSettingMap.get('screenWidthTime', '1'))
    window1.screenWidthNode.setValidator(intPositiveValidator)
    window1.screenWidthNode.setFixedWidth(60)
    plotheaderLine1.addWidget(window1.screenWLabel)
    plotheaderLine1.addWidget(window1.screenWidthNode)
    window1.saveDataNode2 = QPushButton(window1.langData.get('save_data_btn'), clicked=window1.exportMonitorDataCSV)
    plotheaderLine1.addWidget(window1.saveDataNode2)
    window1.openDataNode2 = QPushButton(window1.langData.get('open_history_data'), clicked=window1.openMonitorDatafile)
    plotheaderLine1.addWidget(window1.openDataNode2)
    window1.resetNode2 = QPushButton(window1.langData.get('refresh_plot'))
    window1.resetNode2.clicked.connect(window1.resetMonitorChart)
    plotheaderLine1.addWidget(window1.resetNode2)
    clear_graph_outputNode2 = QPushButton(window1.langData.get('clear_display'), clicked=window1.clear_monitor_graph)
    plotheaderLine1.addWidget(clear_graph_outputNode2)
    window1.toggleCursorBtn2 = QCheckBox(window1.langData.get('plot_tip'))
    window1.toggleCursorBtn2.toggled.connect(window1.toggle_Cursor2)
    plotheaderLine1.addWidget(window1.toggleCursorBtn2)
    chk2_mouseXEnable = QCheckBox(window1.langData.get('set_mouseX_enable'))
    chk2_mouseXEnable.toggled.connect(window1.set_mouseXEnable2)
    plotheaderLine1.addWidget(chk2_mouseXEnable)
    chk2_mouseYEnable = QCheckBox(window1.langData.get('set_mouseY_enable'))
    chk2_mouseYEnable.toggled.connect(window1.set_mouseYEnable2)
    plotheaderLine1.addWidget(chk2_mouseYEnable)
    plotheaderLine1.addStretch(1)
    plot_rx_label = QLabel('{}: 0'.format(window1.langData.get('channel_data_counts')))
    plot_rx_label.setFixedWidth(100)
    plotheaderLine1.addWidget(plot_rx_label)
    set_all_buttons_noFocus(plotheaderLine1)
    plotvlayout = QVBoxLayout()
    plotvlayout.addLayout(plotheaderLine1)
    # 设置画图部分#初始化图形界面2
    window1.initPlotMonitorGraph() #调试方便临时注释
    plotvlayout.addWidget(window1.graph_widget)
    #调试方便临时注释
    plotvlayout.setContentsMargins(3, 3, 3, 3)
    plotMonitorDialog.setLayout(plotvlayout)
    # 新创建一个导入导出的弹框
    ioDialog = QDialog(window1)
    ioDialog.setWindowIcon( QIcon('./icons/import3.png'))
    ioDialog.setWindowTitle(window1.langData.get('register_cfg'))
    ioDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    ioDialog.finished.connect(window1.recordDialogFinished)
    ioDialog.resize(700, 400)
    # 添加导入操作的区域
    btnLineLayout = QHBoxLayout()
    importCsvbtn = QPushButton(window1.langData.get('open_csv'), clicked=window1.openCSVfile)
    importPwfbtn = QPushButton(window1.langData.get('open_pwf'), clicked=window1.openPWFfile)
    btnLineLayout.addWidget(importCsvbtn)
    btnLineLayout.addWidget(importPwfbtn)
    stationAddrNode = QLabel(window1.langData.get('station_address'))
    window1.stationNum = QLineEdit(window1.configSettingMap.get('ioSlaveAddr', '1'))
    window1.stationNum.setValidator(slaveAddrValidator)
    window1.stationNum.setFixedWidth(40)
    btnLineLayout.addWidget(stationAddrNode)
    btnLineLayout.addWidget(window1.stationNum)
    readRawValBtn = QPushButton(window1.langData.get('read_raw_value'), clicked=window1.readRawValue)
    writeListBtn = QPushButton(window1.langData.get('write_btn'), clicked=window1.writeItemList)
    multiWriteListBtn = QPushButton(window1.langData.get('write_batch'), clicked=window1.writeBatchList)
    savecsvBtn = QPushButton(window1.langData.get('saveAs_csv'), clicked=window1.saveCSVfile)
    savepwfBtn = QPushButton(window1.langData.get('saveAs_pwf'), clicked=window1.savePWFfile)
    btnLineLayout.addWidget(readRawValBtn)
    btnLineLayout.addWidget(writeListBtn)
    btnLineLayout.addWidget(multiWriteListBtn)
    btnLineLayout.addWidget(savecsvBtn)
    btnLineLayout.addWidget(savepwfBtn)
    # 设置按钮不要自动聚焦，方便用户使用
    set_all_buttons_noFocus(btnLineLayout)
    savecsvBtn.setEnabled(False)
    savepwfBtn.setEnabled(False)
    # 设置第一行的所有的节点的样式宽度不超过80px
    #
    # for nx in range(btnLineLayout.count()): # btnLineLayout.itemAt(nx).widget().setStyleSheet('max-width:100px;') # 添加到导入导出弹框布局中去
    ioTableList = QTableWidget()
    ioTableList.setColumnCount(4)
    # 启用排序功能
    # ioTableList.setSortingEnabled(True)
    ioTableList.setHorizontalHeaderLabels([window1.langData.get('write_address'), window1.langData.get('write_value'),window1.langData.get('raw_value'),window1.langData.get('write_state')])
    ioTableList.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    ioTableList.verticalHeader().setDefaultSectionSize(23)
    ioDialogVbox = QVBoxLayout()
    ioDialogVbox.addLayout(btnLineLayout)
    ioDialogVbox.addWidget(ioTableList)
    ioDialog.setLayout(ioDialogVbox)
    # 新创建一个通道选择的弹框
    channelDialog = QDialog(window1)
    channelDialog.setWindowIcon( QIcon('./icons/datawave.png'))
    channelDialog.setWindowTitle(window1.langData.get('select_channel'))
    channelDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    channelDialog.finished.connect(window1.recordDialogFinished)
    channelDialog.resize(900, 600)
    # 添加头部组件
    selectChannel_hbox = QHBoxLayout()
    filterSearchLabel = QLabel(window1.langData.get('filter_search_select'))
    selectChannel_hbox.addWidget(filterSearchLabel)
    window1.filterSearch = ExtendedComboBox(window1)
    selectChannel_hbox.addWidget(window1.filterSearch)
    selectChannel_hbox.addStretch(1)
    confirmBtnNode=QPushButton(window1.langData.get('confirm_btn'), clicked=window1.confirmBtnClicked)
    selectChannel_hbox.addWidget(confirmBtnNode)
    resetBtnNode=QPushButton(window1.langData.get('reset_btn'), clicked=window1.resetBtnClicked)
    selectChannel_hbox.addWidget(resetBtnNode)
    set_all_buttons_noFocus(selectChannel_hbox)
    hbox_wrapper = QGroupBox(window1.langData.get('setting'))
    hbox_wrapper.setLayout(selectChannel_hbox)
    hbox_wrapper.setStyleSheet('QPushButton{ max-width:80px;}')
    window1.channelGrid = QGridLayout()
    window1.renderchannelGrid()
    # 1.添加到滚动区域内
    wrapperwid = QWidget()
    wrapperwid.setLayout(window1.channelGrid)
    wrapperwid.setStyleSheet('QCheckBox:checked{ background:yellow;}')
    scroll_area_wrapper = QScrollArea()
    scroll_area_wrapper.setWidgetResizable(True)
    scroll_area_wrapper.setWidget(wrapperwid)
    selectChannel_vbox = QVBoxLayout()
    selectChannel_vbox.addWidget(hbox_wrapper)
    selectChannel_vbox.addWidget(scroll_area_wrapper)
    channelDialog.setLayout(selectChannel_vbox)
    channelDialog.setWindowModality(Qt.ApplicationModal)
    otaDialog = QDialog(window1)
    otaDialog.setWindowTitle(window1.langData.get('ota_update_dialog'))
    otaDialog.setWindowIcon( QIcon('./icons/fileUpdate.png'))
    otaDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    otaDialog.finished.connect(window1.otaDialogFinished)
    otaDialog.resize(700, 400)
    otaWrapperGrid = QVBoxLayout()
    otaDialog.setLayout(otaWrapperGrid)
    # 设置串口区域
    window1.ota_setting_box = QGroupBox(window1.langData.get('ota_setting'))
    ota_setting_layout1 = QGridLayout()
    window1.ota_setting_box.setLayout(ota_setting_layout1)
    otaWrapperGrid.addWidget(window1.ota_setting_box)
    otaSlaveAddrLabel = QLabel(window1.langData.get('station_address'))
    ota_setting_layout1.addWidget(otaSlaveAddrLabel,1,0)
    window1.devInputNode = QLineEdit(window1.configSettingMap.get('otaSlaveAddr', '1'))
    window1.devInputNode.setValidator(slaveAddrValidator)
    ota_setting_layout1.addWidget(window1.devInputNode,1,1)
    otaUpdateDev = QLabel(window1.langData.get('update_dev'))
    ota_setting_layout1.addWidget(otaUpdateDev,1,2)
    window1.otaUpdateList = QComboBox()
    window1.otaUpdateList.addItems(['0=EMS','1=DSP','2=BMS'])
    window1.otaUpdateList.setEditable(True)
    ota_setting_layout1.addWidget(window1.otaUpdateList,1,3)
    otaFileSizelabel = QLabel(window1.langData.get('file_size'))
    ota_setting_layout1.addWidget(otaFileSizelabel,2,0)
    window1.sizeInputNode = QLineEdit('')
    window1.sizeInputNode.setEnabled(False)
    ota_setting_layout1.addWidget(window1.sizeInputNode,2,1)
    otaFilecrcLabel = QLabel(window1.langData.get('file_crc'))
    ota_setting_layout1.addWidget(otaFilecrcLabel,2,2)
    window1.crcInputNode = QLineEdit('0x0')
    window1.crcInputNode.setEnabled(False)
    ota_setting_layout1.addWidget(window1.crcInputNode,2,3)
    otaFileByteLen = QLabel(window1.langData.get('byte_len'))
    ota_setting_layout1.addWidget(otaFileByteLen,2,4)
    window1.byteLenInputNode = QLineEdit('1024')
    ota_setting_layout1.addWidget(window1.byteLenInputNode,2,5)
    otaFileBin = QLabel(window1.langData.get('ota_file'))
    ota_setting_layout1.addWidget(otaFileBin,3,0)
    window1.otaFileInputNode = QLineEdit('')
    window1.otaFileInputNode.setEnabled(False)
    ota_setting_layout1.addWidget(window1.otaFileInputNode,3,1,1,4)
    window1.readTriggerBtn = QPushButton(window1.langData.get('read_file'), clicked=window1.readFileTrigger)
    window1.readTriggerBtn.setFocusPolicy(Qt.NoFocus)
    ota_setting_layout1.addWidget(window1.readTriggerBtn,3,5)
    # 设置state_区域
    window1.ota_state_box = QGroupBox(window1.langData.get('ota_state'))
    ota_setting_layout2 = QGridLayout()
    window1.ota_state_box.setLayout(ota_setting_layout2)
    otaWrapperGrid.addWidget(window1.ota_state_box)
    otaSNlabel = QLabel(window1.langData.get('ota_sn'))
    ota_setting_layout2.addWidget(otaSNlabel,1,0)
    window1.devSNnode = QLineEdit('')
    window1.devSNnode.setDisabled(True)
    # window1.devSNnode.setStyleSheet('background:#eee;')
    ota_setting_layout2.addWidget(window1.devSNnode,1,1,1,4)
    otaVersionlabel = QLabel(window1.langData.get('ota_version'))
    ota_setting_layout2.addWidget(otaVersionlabel,2,0)
    window1.devVersionnode = QLineEdit('')
    window1.devVersionnode.setDisabled(True)
    # window1.devVersionnode.setStyleSheet('background:#eee;')
    ota_setting_layout2.addWidget(window1.devVersionnode,2,1,1,4)
    window1.readDevBtn = QPushButton(window1.langData.get('read_info'), clicked=window1.getDevInfoTrigger)
    window1.readDevBtn.setFocusPolicy(Qt.NoFocus)
    ota_setting_layout2.addWidget(window1.readDevBtn,2,5)
    # 设置operation_区域
    window1.ota_operation_box = QGroupBox(window1.langData.get('update_operation'))
    ota_setting_layout3 = QGridLayout()
    window1.ota_operation_box.setLayout(ota_setting_layout3)
    otaWrapperGrid.addWidget(window1.ota_operation_box)
    updateStatelabel = QLabel(window1.langData.get('update_state'))
    ota_setting_layout3.addWidget(updateStatelabel,1,0)
    window1.updateTiptext = QLineEdit(window1.langData.get('update_state'))
    window1.updateTiptext.setEnabled(False)
    ota_setting_layout3.addWidget(window1.updateTiptext,1,1,1,4)
    updateProgresslabel = QLabel(window1.langData.get('update_progress'))
    ota_setting_layout3.addWidget(updateProgresslabel,2,0)
    #进度条1 正常普通进度条
    window1.progressbar01 = QProgressBar(window1,minimum=0, maximum=100, objectName="progressbar01")
    window1.progressbar01.setMinimum(0)
    window1.progressbar01.setMaximum(100)
    #设置最大值 最小值
    ota_setting_layout3.addWidget(window1.progressbar01,2,1,1,4)
    window1.updateTriggerBtn = QPushButton(window1.langData.get('update_start'), clicked=window1.updateRequestTrigger)
    window1.updateTriggerBtn.setFocusPolicy(Qt.NoFocus)
    ota_setting_layout3.addWidget(window1.updateTriggerBtn,2,5)
    # 添加配置通道偏移相关的弹框界面、节点等
    settingDialog = QDialog(window1)
    settingDialog.setWindowIcon( QIcon('./icons/datawave.png'))
    settingDialog.setWindowTitle(window1.langData.get('set_channel'))
    settingDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    settingDialog.finished.connect(window1.recordDialogFinished)
    settingDialog.resize(600, 300)
    settingDialog.setStyleSheet('font-size:11px;')
    setChannelVbox = QVBoxLayout()
    settingDialog.setLayout(setChannelVbox)
    channelTableList = QTableWidget()
    channelTableList.setColumnCount(9)
    channelTableList.setHorizontalHeaderLabels([window1.langData.get('data_address'), window1.langData.get('data_name'), window1.langData.get('channel_color'), window1.langData.get('channel_y_scale'), window1.langData.get('channel_y_offset'), 'XA-XB','YA','YB','YA-YB'])
    # 可以设置tableview所有列的默认行高为15。
    channelTableList.verticalHeader().setDefaultSectionSize(24)
    # channelTableList.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    #自动分配列宽，不可手动调整
    # channelTableList.horizontalHeader().setMinimumSectionSize(40)
    # channelTableList.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
    channelTableList.setColumnWidth(0,70)
    channelTableList.setColumnWidth(1,60)
    channelTableList.setColumnWidth(2,70)
    channelTableList.setColumnWidth(3,70)
    channelTableList.setColumnWidth(4,70)
    channelTableList.setColumnWidth(5,50)
    channelTableList.setColumnWidth(6,50)
    channelTableList.setColumnWidth(7,50)
    channelTableList.setColumnWidth(8,50)
    channelTableList.itemClicked.connect(window1.channelItemClick)
    setChannelResetbtn = QPushButton(window1.langData.get('reset_btn'), clicked=window1.setChannelResetClicked)
    setChannelVbox.addWidget(setChannelResetbtn)
    setChannelResetbtn.setFocusPolicy(Qt.NoFocus)
    setChannelResetbtn.setFixedWidth(60)
    setChannelVbox.addWidget(channelTableList)
    # 添加密码输入&管理员等级相关的弹框界面、节点等
    passwordDialog = QDialog(window1)
    passwordDialog.setWindowIcon(QIcon('./icons/passwordset.png'))
    passwordDialog.setWindowTitle(window1.langData.get('password_management'))
    passwordDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    passwordDialog.setWindowModality(Qt.ApplicationModal)
    #是否保证最上层操作
    passwordDialog.finished.connect(window1.recordDialogFinished)
    passwordDialog.resize(450, 300)
    # 添加密码权限管理表格【列表一栏】
    pwdTableList = QTableWidget()
    pwdTableList.setColumnCount(4)
    pwdTableList.setHorizontalHeaderLabels(['功能','权限1','权限2','权限3'])
    # pwdTableList.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    pwdTableList.verticalHeader().setDefaultSectionSize(23)
    permissionList = [ ['数据监控', '✓', '✓', '✓'], ['数据记录', '✓', '✓', '✓'], ['数据读写', 'x', 'x', '✓'], ['参数配置', 'x', 'x', '✓'], ['文件上传', 'x', '✓', '✓'], ['OTA升级', 'x', 'x', '✓'], ['实时波形展示', 'x', '✓', '✓'], ['软件示波器', 'x', 'x', '✓'], ]
    pwdTableList.setRowCount(len(permissionList))
    for (row,item) in enumerate(permissionList):
        functionNameItem = QTableWidgetItem(item[0])
        functionNameItem.setToolTip(item[0])
        permission1_1 = QTableWidgetItem(item[1])
        permission1_2 = QTableWidgetItem(item[2])
        permission1_3 = QTableWidgetItem(item[3])
        permission1_1.setTextAlignment(Qt.AlignHCenter)
        permission1_2.setTextAlignment(Qt.AlignHCenter)
        permission1_3.setTextAlignment(Qt.AlignHCenter)
        pwdTableList.setItem(row, 0, functionNameItem)
        pwdTableList.setItem(row, 1, permission1_1)
        pwdTableList.setItem(row, 2, permission1_2)
        pwdTableList.setItem(row, 3, permission1_3)
    pwdTableList.setDisabled(True)
    passwordHbox = QHBoxLayout()
    pwdLevel = QLabel(window1.langData.get('pwd_level'))
    passwordHbox.addWidget(pwdLevel)
    passwordNode = QLineEdit('')
    passwordNode.setFixedWidth(60)
    pwdsetbtn = QPushButton('OK', clicked=window1.pwdConfirmSet)
    pwdsetbtn.setFocusPolicy(Qt.NoFocus)
    passwordHbox.addStretch(1)
    passwordHbox.addWidget(passwordNode)
    passwordHbox.addWidget(pwdsetbtn)
    passwordVbox = QVBoxLayout()
    passwordVbox.addWidget(pwdTableList)
    passwordVbox.addLayout(passwordHbox)
    passwordDialog.setLayout(passwordVbox)
    # 添加串口配置相关的弹框界面、节点等
    comSetDialog = QDialog(window1)
    comSetDialog.setWindowIcon(QIcon('./icons/setting3.png'))
    comSetDialog.setWindowTitle(window1.langData.get('communncation_set'))
    comSetDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    comSetDialog.finished.connect(window1.recordDialogFinished)
    comSetDialog.resize(200, 200)
    comformLayout = QFormLayout()
    comformLayout.setSpacing(10)
    comSetDialog.setLayout(comformLayout)
    comDatabitsList = QComboBox()
    comDatabitsList.addItems(['5','6','7','8'])
    comDatabitsList.setCurrentText('8')
    comStopbitsList = QComboBox()
    comStopbitsList.addItems(['1', '1.5', '2'])
    comParityList = QComboBox()
    comParityList.addItems(["None","Odd","Even","Mark","Space"])
    comFlowconList = QComboBox()
    comFlowconList.addItems(["None","Hardware","Software","Custom"])
    comsetbtn = QPushButton('OK', clicked=window1.confirmComSet)
    comsetbtn.setFocusPolicy(Qt.NoFocus)
    comformLayout.addRow(QLabel('Data bits'), comDatabitsList)
    comformLayout.addRow(QLabel('Stop bits'), comStopbitsList)
    comformLayout.addRow(QLabel('Parity'), comParityList)
    comformLayout.addRow(QLabel('Flow control'), comFlowconList)
    comformLayout.addRow(QLabel('---'), QLabel('---'))
    # 新增常用参数设置的弹框
    # pollingSize---writeWaitTime
    paramSetdelayTime = QLineEdit(str(window1.updateStampWaitTime))
    paramSetReadTime = QLineEdit(str(window1.loopWaitTime))
    paramSetWriteTime = QLineEdit(str(window1.writeWaitTime))
    paramSetFileSize = QLineEdit(str(window1.maxfileSize))
    paramSetSaveInterval = QLineEdit(str(window1.autoSaveInterval))
    paramSetSleepInterval = QLineEdit(str(int(window1.sleepTime*1000)))
    # 给输入框添加正整数验证，不允许小数点等
    paramSetdelayTime.setValidator(intPositiveValidator)
    paramSetReadTime.setValidator(intPositiveValidator)
    paramSetWriteTime.setValidator(intPositiveValidator)
    paramSetFileSize.setValidator(intPositiveValidator)
    paramSetSaveInterval.setValidator(intPositiveValidator)
    paramSetSleepInterval.setValidator(intPositiveValidator)
    comformLayout.addRow(QLabel('收与发间隔时间[ms]'), paramSetSleepInterval)
    comformLayout.addRow(QLabel('更新时间戳间隔时间[ms]'), paramSetdelayTime)
    comformLayout.addRow(QLabel('读取响应超时时间[ms]'), paramSetReadTime)
    comformLayout.addRow(QLabel('写入响应超时时间[ms]'), paramSetWriteTime)
    comformLayout.addRow(QLabel('自动保存的间隔时间[s]'), paramSetSaveInterval)
    comformLayout.addRow(QLabel('日志文件大小的最大值[M]'), paramSetFileSize)
    comformLayout.addRow(QLabel(''), comsetbtn)
    # 选择并勾选设置通道的弹框区域
    addressDialog = QDialog(window1)
    addressDialog.setWindowTitle(window1.langData.get('channel_address_dialog'))
    addressDialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    addressDialog.finished.connect(window1.recordDialogFinished)
    # 添加一些相关的功能按钮
    settingConfirmBtn = QPushButton(window1.langData.get('set_address_confirmBtn'), clicked=window1.settingConfirmEvent)
    addOneBtnNode = QPushButton(window1.langData.get('set_address_addBtn'), clicked=window1.addOneBtnClicked)
    addOneBtnNode.setIcon(QIcon('./icons/round_add.png'))
    addrHbox1 = QHBoxLayout()
    addrHbox1.addWidget(addOneBtnNode)
    addrHbox1.addWidget(settingConfirmBtn)
    addrHbox1.addStretch(1)
    set_all_buttons_noFocus(addrHbox1)
    # addrHbox1.addWidget(delOneBtnNode)
    # 设置地址的表格管理
    addrTableList = QTableWidget()
    addrTableList.setColumnCount(7)
    # addrTableList.setSelectionBehavior(QAbstractItemView.SelectRows)#设置表格的选取方式是行选取
    # addrTableList.setSelectionMode(QAbstractItemView.SingleSelection)#设置选取方式为单个选取
    addrTableList.setHorizontalHeaderLabels(['ID', window1.langData.get('data_name'), window1.langData.get('data_address'), window1.langData.get('data_offset'), window1.langData.get('data_type'), window1.langData.get('data_precision'), window1.langData.get('data_operate')])
    addrTableList.verticalHeader().setDefaultSectionSize(23)
    # addrTableList.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    #自动分配列宽，不可手动调整
    addrTableList.setColumnWidth(0, 50)
    addrTableList.setColumnWidth(1, 120)
    addrTableList.setColumnWidth(2, 80)
    addrTableList.setColumnWidth(3, 50)
    addrTableList.setColumnWidth(4, 60)
    addrTableList.setColumnWidth(5, 60)
    addrTableList.setColumnWidth(6, 40)
    window1.readTableCFG()
    settingbtnBox = QVBoxLayout()
    settingbtnBox.addLayout(addrHbox1)
    settingbtnBox.addWidget(addrTableList)
    # settingbtnBox.addStretch(1)
    addressDialog.setLayout(settingbtnBox)
    addressDialog.resize(500, 300)
    # 弹框节点结束
    # import pdb
    # pdb.set_trace()
    # 进入pdb调试模式
    sys.exit(app.exec())

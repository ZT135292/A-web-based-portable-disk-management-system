"""
移动硬盘管理系统 - 主应用文件
"""

import os
import csv
import io
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, redirect, url_for, request,
    flash, session, jsonify, Response
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from i18n import (
    _, get_locale, translate_action, translate_admin_note, translate_audit_details,
    status_label, status_badge, importance_labels, backup_labels,
    format_date, format_datetime, SUPPORTED_LANGUAGES,
)

app = Flask(__name__)
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError(
        '未设置 SECRET_KEY 环境变量。'
        '请运行：set SECRET_KEY=<你的随机密钥>  然后再启动服务。'
        '生成密钥：python -c "import secrets; print(secrets.token_hex(32))"'
    )
app.secret_key = _secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///disk_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ──────────────────────────────────────────────
# 数据库模型
# ──────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name  = db.Column(db.String(120))
    email         = db.Column(db.String(120))
    department    = db.Column(db.String(120))
    role          = db.Column(db.String(20), default='user')   # 'admin' or 'user'
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    disks         = db.relationship('Disk', backref='manager', lazy=True,
                                    foreign_keys='Disk.manager_id')
    requests      = db.relationship('DiskRequest', backref='requester', lazy=True,
                                    foreign_keys='DiskRequest.user_id')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Disk(db.Model):
    __tablename__ = 'disks'
    id               = db.Column(db.Integer, primary_key=True)
    disk_number      = db.Column(db.String(60), unique=True, nullable=False)  # 编号
    disk_type        = db.Column(db.String(30), default='HDD')                # HDD/SSD/NVMe
    total_space_gb   = db.Column(db.Float, default=0)
    used_space_gb    = db.Column(db.Float, default=0)
    status           = db.Column(db.String(30), default='idle')               # active/idle/faulty/maintenance
    location         = db.Column(db.String(256))                              # 所在地点
    brand            = db.Column(db.String(120))                              # 品牌
    model_name       = db.Column(db.String(120))                              # 型号
    serial_number    = db.Column(db.String(120))                              # S/N 序列号
    part_number      = db.Column(db.String(120))                              # P/N 产品编号
    manager_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    management_start = db.Column(db.Date, nullable=True)
    notes            = db.Column(db.Text, default='')
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    data_entries         = db.relationship('DataEntry', backref='disk', lazy=True,
                                           cascade='all, delete-orphan')
    requests             = db.relationship('DiskRequest', backref='disk', lazy=True,
                                           cascade='all, delete-orphan')
    history              = db.relationship('ManagementHistory', backref='disk', lazy=True,
                                           cascade='all, delete-orphan')
    audit_logs           = db.relationship('AuditLog', backref='disk', lazy=True,
                                           cascade='all, delete-orphan')

    @property
    def free_space_gb(self):
        return max(0, self.total_space_gb - self.used_space_gb)

    @property
    def usage_percent(self):
        if self.total_space_gb <= 0:
            return 0
        return min(100, round(self.used_space_gb / self.total_space_gb * 100, 1))


class DataEntry(db.Model):
    """硬盘内存储的数据条目"""
    __tablename__ = 'data_entries'
    id              = db.Column(db.Integer, primary_key=True)
    disk_id         = db.Column(db.Integer, db.ForeignKey('disks.id'), nullable=False)
    description     = db.Column(db.String(512), nullable=False)   # 数据描述
    data_path       = db.Column(db.String(512))                   # 路径
    size_gb         = db.Column(db.Float, default=0)              # 数据大小 GB
    importance      = db.Column(db.String(20), default='normal')  # critical/important/normal/temp
    backup_status   = db.Column(db.String(20), default='unknown') # backed_up/not_backed/unknown
    backup_location = db.Column(db.String(512))                    # 备份位置
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiskRequest(db.Model):
    """用户申请管理硬盘 / 申请退还硬盘"""
    __tablename__ = 'disk_requests'
    id           = db.Column(db.Integer, primary_key=True)
    disk_id      = db.Column(db.Integer, db.ForeignKey('disks.id'), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_type = db.Column(db.String(20), default='manage')     # manage / return
    reason       = db.Column(db.Text)                              # 申请理由
    status       = db.Column(db.String(20), default='pending')    # pending/approved/rejected
    admin_note   = db.Column(db.Text)                             # 管理员备注
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at  = db.Column(db.DateTime, nullable=True)
    resolved_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class ManagementHistory(db.Model):
    """硬盘管理员变更历史"""
    __tablename__ = 'management_history'
    id           = db.Column(db.Integer, primary_key=True)
    disk_id      = db.Column(db.Integer, db.ForeignKey('disks.id'), nullable=False)
    manager_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    start_date   = db.Column(db.Date)
    end_date     = db.Column(db.Date, nullable=True)
    note         = db.Column(db.String(512))
    manager      = db.relationship('User', foreign_keys=[manager_id])


class AuditLog(db.Model):
    """操作审计日志"""
    __tablename__ = 'audit_logs'
    id         = db.Column(db.Integer, primary_key=True)
    disk_id    = db.Column(db.Integer, db.ForeignKey('disks.id'), nullable=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action     = db.Column(db.String(100))
    details    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user       = db.relationship('User', foreign_keys=[user_id])


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def add_audit(action, details, disk_id=None, user_id=None):
    uid = user_id or session.get('user_id')
    log = AuditLog(disk_id=disk_id, user_id=uid, action=action, details=details)
    db.session.add(log)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash(_('flash.login_required'), 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash(_('flash.login_required'), 'warning')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            flash(_('flash.admin_required'), 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def pending_count():
    return DiskRequest.query.filter_by(status='pending').count()

app.jinja_env.globals['current_user'] = current_user
app.jinja_env.globals['pending_count'] = pending_count
app.jinja_env.globals['_'] = _
app.jinja_env.globals['translate_action'] = translate_action
app.jinja_env.globals['translate_admin_note'] = translate_admin_note
app.jinja_env.globals['translate_audit_details'] = translate_audit_details
app.jinja_env.globals['status_label'] = status_label
app.jinja_env.globals['status_badge'] = status_badge
app.jinja_env.globals['format_date'] = format_date
app.jinja_env.globals['format_datetime'] = format_datetime


@app.context_processor
def inject_i18n():
    return {
        'lang': get_locale(),
        'IMPORTANCE_LABELS': importance_labels(),
        'BACKUP_LABELS': backup_labels(),
    }


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}


@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in SUPPORTED_LANGUAGES:
        session['lang'] = lang
        flash(_('flash.language_changed'), 'info')
    return redirect(request.referrer or url_for('login'))


# ──────────────────────────────────────────────
# 认证路由
# ──────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(_('flash.welcome_back', name=user.display_name or user.username), 'success')
            return redirect(url_for('dashboard'))
        flash(_('flash.bad_credentials'), 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username     = request.form.get('username', '').strip()
        password     = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        email        = request.form.get('email', '').strip()
        department   = request.form.get('department', '').strip()

        if not username or not password:
            flash(_('flash.username_password_required'), 'danger')
            return render_template('register.html')

        if not display_name:
            flash(_('flash.display_name_required'), 'danger')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash(_('flash.username_exists'), 'danger')
            return render_template('register.html')

        user = User(
            username=username,
            display_name=display_name,
            email=email,
            department=department,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(_('flash.register_success'), 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash(_('flash.logged_out'), 'info')
    return redirect(url_for('login'))


# ──────────────────────────────────────────────
# 仪表板
# ──────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    total_disks   = Disk.query.count()
    active_disks  = Disk.query.filter_by(status='active').count()
    idle_disks    = Disk.query.filter_by(status='idle').count()
    faulty_disks  = Disk.query.filter_by(status='faulty').count()

    all_disks     = Disk.query.all()
    total_space   = sum(d.total_space_gb for d in all_disks)
    used_space    = sum(d.used_space_gb for d in all_disks)

    pending_req   = DiskRequest.query.filter_by(status='pending').count()
    my_disks      = Disk.query.filter_by(manager_id=session['user_id']).all()

    user = current_user()
    if user.role == 'admin':
        recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    else:
        recent_logs = AuditLog.query.filter_by(user_id=session['user_id'])\
                                    .order_by(AuditLog.created_at.desc()).limit(8).all()

    return render_template('dashboard.html',
        total_disks=total_disks, active_disks=active_disks,
        idle_disks=idle_disks, faulty_disks=faulty_disks,
        total_space=total_space, used_space=used_space,
        pending_req=pending_req, my_disks=my_disks,
        recent_logs=recent_logs
    )


# ──────────────────────────────────────────────
# 硬盘列表
# ──────────────────────────────────────────────

@app.route('/disks')
@login_required
def disks():
    q          = request.args.get('q', '').strip()
    status     = request.args.get('status', '')
    dtype      = request.args.get('dtype', '')
    manager_id = request.args.get('manager_id', '')

    query = Disk.query
    if q:
        query = query.outerjoin(User, Disk.manager_id == User.id).filter(
            db.or_(
                Disk.disk_number.ilike(f'%{q}%'),
                Disk.brand.ilike(f'%{q}%'),
                Disk.model_name.ilike(f'%{q}%'),
                Disk.serial_number.ilike(f'%{q}%'),
                Disk.part_number.ilike(f'%{q}%'),
                Disk.location.ilike(f'%{q}%'),
                Disk.notes.ilike(f'%{q}%'),
                User.display_name.ilike(f'%{q}%'),
                User.username.ilike(f'%{q}%'),
            )
        )
    if status:
        query = query.filter_by(status=status)
    if dtype:
        query = query.filter_by(disk_type=dtype)
    if manager_id == 'none':
        query = query.filter(Disk.manager_id.is_(None))
    elif manager_id:
        try:
            query = query.filter_by(manager_id=int(manager_id))
        except ValueError:
            pass

    sort = request.args.get('sort', '')
    if sort == 'free_desc':
        disk_list = sorted(query.all(), key=lambda d: d.free_space_gb, reverse=True)
    else:
        disk_list = query.order_by(Disk.disk_number).all()

    managers  = User.query.order_by(User.display_name).all()
    return render_template('disks.html', disks=disk_list, q=q, status=status,
                           dtype=dtype, manager_id=manager_id, managers=managers, sort=sort)


@app.route('/disks/export')
@login_required
def export_disks():
    disks = Disk.query.order_by(Disk.disk_number).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        _('csv.disk_number'), _('csv.disk_type'), _('csv.status'),
        _('csv.total_gb'), _('csv.used_gb'), _('csv.free_gb'), _('csv.usage_pct'),
        _('csv.location'), _('csv.brand'), _('csv.model'),
        _('csv.serial'), _('csv.part'), _('csv.manager'), _('csv.mgmt_start'), _('csv.notes'),
    ])
    for d in disks:
        writer.writerow([
            d.disk_number, d.disk_type, status_label(d.status),
            d.total_space_gb, d.used_space_gb, d.free_space_gb, d.usage_percent,
            d.location or '', d.brand or '', d.model_name or '',
            d.serial_number or '', d.part_number or '',
            d.manager.display_name if d.manager else '',
            d.management_start.strftime('%Y-%m-%d') if d.management_start else '',
            d.notes or ''
        ])
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=disks_export.csv'}
    )


# ──────────────────────────────────────────────
# 硬盘详情
# ──────────────────────────────────────────────

@app.route('/disks/<int:disk_id>')
@login_required
def disk_detail(disk_id):
    disk = Disk.query.get_or_404(disk_id)
    pending_my_req = DiskRequest.query.filter_by(
        disk_id=disk_id, user_id=session['user_id'], status='pending', request_type='manage'
    ).first()
    pending_return_req = DiskRequest.query.filter_by(
        disk_id=disk_id, user_id=session['user_id'], status='pending', request_type='return'
    ).first()
    return render_template('disk_detail.html', disk=disk,
                           pending_my_req=pending_my_req,
                           pending_return_req=pending_return_req)


@app.route('/disks/<int:disk_id>/update_space', methods=['POST'])
@login_required
def update_space(disk_id):
    disk = Disk.query.get_or_404(disk_id)
    user = current_user()

    if disk.manager_id != user.id and user.role != 'admin':
        flash(_('flash.no_permission_space'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    try:
        used = float(request.form.get('used_space_gb', disk.used_space_gb))
        total = float(request.form.get('total_space_gb', disk.total_space_gb))
        if used < 0 or total < 0:
            raise ValueError
    except ValueError:
        flash(_('flash.invalid_number'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    old_used = disk.used_space_gb
    disk.used_space_gb  = used
    disk.total_space_gb = total
    disk.updated_at     = datetime.utcnow()
    add_audit('audit.update_space',
              _('audit.update_space_detail', old=old_used, used=used, total=total),
              disk_id=disk_id)
    db.session.commit()
    flash(_('flash.space_updated'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk_id))


@app.route('/disks/<int:disk_id>/update_notes', methods=['POST'])
@login_required
def update_notes(disk_id):
    disk = Disk.query.get_or_404(disk_id)
    user = current_user()

    if disk.manager_id != user.id and user.role != 'admin':
        flash(_('flash.no_permission_notes'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    disk.notes      = request.form.get('notes', '')
    disk.updated_at = datetime.utcnow()
    add_audit('audit.update_notes', '', disk_id=disk_id)
    db.session.commit()
    flash(_('flash.notes_saved'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk_id))


# ──────────────────────────────────────────────
# 数据条目（描述+路径）
# ──────────────────────────────────────────────

@app.route('/disks/<int:disk_id>/data/add', methods=['POST'])
@login_required
def add_data_entry(disk_id):
    disk = Disk.query.get_or_404(disk_id)
    user = current_user()

    if disk.manager_id != user.id and user.role != 'admin':
        flash(_('flash.no_permission_add_data'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    desc           = request.form.get('description', '').strip()
    path           = request.form.get('data_path', '').strip()
    importance     = request.form.get('importance', 'normal')
    backup         = request.form.get('backup_status', 'unknown')
    backup_loc     = request.form.get('backup_location', '').strip()
    try:
        size = float(request.form.get('size_gb', 0) or 0)
    except ValueError:
        size = 0

    if not desc:
        flash(_('flash.description_required'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    entry = DataEntry(
        disk_id=disk_id, description=desc, data_path=path,
        size_gb=size, importance=importance, backup_status=backup,
        backup_location=backup_loc or None,
        created_by=user.id
    )
    db.session.add(entry)
    add_audit('audit.add_data_entry', desc, disk_id=disk_id)
    db.session.commit()
    flash(_('flash.data_entry_added'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk_id))


@app.route('/data/<int:entry_id>/update', methods=['POST'])
@login_required
def update_data_entry(entry_id):
    entry = DataEntry.query.get_or_404(entry_id)
    disk  = entry.disk
    user  = current_user()

    if disk.manager_id != user.id and user.role != 'admin':
        flash(_('flash.no_permission_edit_entry'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk.id))

    entry.backup_status   = request.form.get('backup_status', entry.backup_status)
    entry.backup_location = request.form.get('backup_location', '').strip() or None
    entry.updated_at      = datetime.utcnow()
    add_audit('audit.update_data_entry_backup', entry.description, disk_id=disk.id)
    db.session.commit()
    flash(_('flash.backup_updated'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk.id))


@app.route('/data/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_data_entry(entry_id):
    entry = DataEntry.query.get_or_404(entry_id)
    disk  = entry.disk
    user  = current_user()

    if disk.manager_id != user.id and user.role != 'admin':
        flash(_('flash.no_permission_delete_entry'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk.id))

    add_audit('audit.delete_data_entry', entry.description, disk_id=disk.id)
    db.session.delete(entry)
    db.session.commit()
    flash(_('flash.data_entry_deleted'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk.id))


# ──────────────────────────────────────────────
# 申请管理硬盘
# ──────────────────────────────────────────────

@app.route('/disks/<int:disk_id>/request', methods=['POST'])
@login_required
def request_disk(disk_id):
    disk   = Disk.query.get_or_404(disk_id)
    user   = current_user()
    reason = request.form.get('reason', '').strip()

    existing = DiskRequest.query.filter_by(
        disk_id=disk_id, user_id=user.id, status='pending'
    ).first()
    if existing:
        flash(_('flash.pending_request_exists'), 'warning')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    if disk.manager_id == user.id:
        flash(_('flash.already_manager'), 'info')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    req = DiskRequest(disk_id=disk_id, user_id=user.id, reason=reason)
    db.session.add(req)
    add_audit('audit.request_manage',
              _('audit.request_manage_detail', disk=disk.disk_number),
              disk_id=disk_id)
    db.session.commit()
    flash(_('flash.request_submitted'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk_id))


@app.route('/disks/<int:disk_id>/return', methods=['POST'])
@login_required
def return_disk(disk_id):
    disk   = Disk.query.get_or_404(disk_id)
    user   = current_user()
    reason = request.form.get('reason', '').strip()

    if disk.manager_id != user.id:
        flash(_('flash.only_manager_can_return'), 'danger')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    existing = DiskRequest.query.filter_by(
        disk_id=disk_id, user_id=user.id, status='pending', request_type='return'
    ).first()
    if existing:
        flash(_('flash.pending_return_exists'), 'warning')
        return redirect(url_for('disk_detail', disk_id=disk_id))

    req = DiskRequest(disk_id=disk_id, user_id=user.id, reason=reason, request_type='return')
    db.session.add(req)
    add_audit('audit.request_return',
              _('audit.request_return_detail', disk=disk.disk_number),
              disk_id=disk_id)
    db.session.commit()
    flash(_('flash.return_submitted'), 'success')
    return redirect(url_for('disk_detail', disk_id=disk_id))


@app.route('/my/requests')
@login_required
def my_requests():
    reqs = DiskRequest.query.filter_by(user_id=session['user_id'])\
                            .order_by(DiskRequest.created_at.desc()).all()
    return render_template('my_requests.html', requests=reqs)


# ──────────────────────────────────────────────
# 管理员路由
# ──────────────────────────────────────────────

@app.route('/admin/requests')
@admin_required
def admin_requests():
    status_filter = request.args.get('status', 'pending')
    query = DiskRequest.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    reqs = query.order_by(DiskRequest.created_at.desc()).all()
    return render_template('admin/requests.html', requests=reqs, status_filter=status_filter)


@app.route('/admin/requests/<int:req_id>/approve', methods=['POST'])
@admin_required
def approve_request(req_id):
    req        = DiskRequest.query.get_or_404(req_id)
    admin_note = request.form.get('admin_note', '')
    disk       = req.disk

    req.status      = 'approved'
    req.admin_note  = admin_note
    req.resolved_at = datetime.utcnow()
    req.resolved_by = session['user_id']

    if req.request_type == 'return':
        # 退还：关闭管理历史，清除管理人
        old_hist = ManagementHistory.query.filter_by(
            disk_id=disk.id, manager_id=disk.manager_id, end_date=None
        ).first()
        if old_hist:
            old_hist.end_date = date.today()

        add_audit('audit.approve_return',
                  _('audit.approve_return_detail',
                    user=req.requester.username, disk=disk.disk_number),
                  disk_id=disk.id)
        disk.manager_id       = None
        disk.management_start = None
        disk.status           = 'idle'

        # 取消该硬盘其他所有退还申请
        DiskRequest.query.filter(
            DiskRequest.disk_id == disk.id,
            DiskRequest.id != req.id,
            DiskRequest.status == 'pending',
            DiskRequest.request_type == 'return'
        ).update({'status': 'rejected', 'admin_note': 'admin_note.other_return_handled',
                  'resolved_at': datetime.utcnow()})
    else:
        # 申请管理：关闭旧管理人历史，建立新历史
        if disk.manager_id:
            old_hist = ManagementHistory.query.filter_by(
                disk_id=disk.id, manager_id=disk.manager_id, end_date=None
            ).first()
            if old_hist:
                old_hist.end_date = date.today()

        hist = ManagementHistory(
            disk_id=disk.id, manager_id=req.user_id, start_date=date.today()
        )
        db.session.add(hist)

        disk.manager_id       = req.user_id
        disk.management_start = date.today()
        disk.status           = 'active'

        # 拒绝同一硬盘的其他待审申请
        DiskRequest.query.filter(
            DiskRequest.disk_id == disk.id,
            DiskRequest.id != req.id,
            DiskRequest.status == 'pending'
        ).update({'status': 'rejected', 'admin_note': 'admin_note.other_request_approved',
                  'resolved_at': datetime.utcnow()})

        add_audit('audit.approve_request',
                  _('audit.approve_request_detail',
                    disk=disk.disk_number, user=req.requester.username),
                  disk_id=disk.id)

    db.session.commit()
    flash(_('flash.request_approved'), 'success')
    return redirect(url_for('admin_requests'))


@app.route('/admin/requests/<int:req_id>/reject', methods=['POST'])
@admin_required
def reject_request(req_id):
    req        = DiskRequest.query.get_or_404(req_id)
    admin_note = request.form.get('admin_note', '')

    req.status       = 'rejected'
    req.admin_note   = admin_note
    req.resolved_at  = datetime.utcnow()
    req.resolved_by  = session['user_id']

    add_audit('audit.reject_request',
              _('audit.reject_request_detail',
                disk=req.disk.disk_number, user=req.requester.username),
              disk_id=req.disk_id)
    db.session.commit()
    flash(_('flash.request_rejected'), 'info')
    return redirect(url_for('admin_requests'))


@app.route('/admin/disks/add', methods=['GET', 'POST'])
@admin_required
def add_disk():
    if request.method == 'POST':
        try:
            total = float(request.form.get('total_space_gb', 0) or 0)
            used  = float(request.form.get('used_space_gb', 0) or 0)
        except ValueError:
            flash(_('flash.invalid_number'), 'danger')
            return render_template('admin/add_disk.html')

        disk = Disk(
            disk_number   = request.form.get('disk_number', '').strip(),
            disk_type     = request.form.get('disk_type', 'HDD'),
            total_space_gb= total,
            used_space_gb = used,
            status        = request.form.get('status', 'idle'),
            location      = request.form.get('location', '').strip(),
            brand         = request.form.get('brand', '').strip(),
            model_name    = request.form.get('model_name', '').strip(),
            serial_number = request.form.get('serial_number', '').strip(),
            part_number   = request.form.get('part_number', '').strip(),
            notes         = request.form.get('notes', '').strip(),
        )
        if not disk.disk_number:
            flash(_('flash.invalid_disk_number'), 'danger')
            return render_template('admin/add_disk.html')

        db.session.add(disk)
        add_audit('audit.add_disk', disk.disk_number)
        db.session.commit()
        flash(_('flash.disk_added', number=disk.disk_number), 'success')
        return redirect(url_for('disks'))
    return render_template('admin/add_disk.html')


@app.route('/admin/disks/<int:disk_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_disk(disk_id):
    disk = Disk.query.get_or_404(disk_id)
    if request.method == 'POST':
        disk.disk_number   = request.form.get('disk_number', disk.disk_number).strip()
        disk.disk_type     = request.form.get('disk_type', disk.disk_type)
        disk.status        = request.form.get('status', disk.status)
        disk.location      = request.form.get('location', '').strip()
        disk.brand         = request.form.get('brand', '').strip()
        disk.model_name    = request.form.get('model_name', '').strip()
        disk.serial_number = request.form.get('serial_number', '').strip()
        disk.part_number   = request.form.get('part_number', '').strip()
        disk.notes         = request.form.get('notes', '').strip()
        try:
            disk.total_space_gb = float(request.form.get('total_space_gb', disk.total_space_gb) or 0)
            disk.used_space_gb  = float(request.form.get('used_space_gb', disk.used_space_gb) or 0)
        except ValueError:
            pass
        disk.updated_at = datetime.utcnow()
        add_audit('audit.edit_disk', disk.disk_number, disk_id=disk_id)
        db.session.commit()
        flash(_('flash.disk_updated'), 'success')
        return redirect(url_for('disk_detail', disk_id=disk_id))
    return render_template('admin/edit_disk.html', disk=disk)


@app.route('/admin/disks/<int:disk_id>/delete', methods=['POST'])
@admin_required
def delete_disk(disk_id):
    disk = Disk.query.get_or_404(disk_id)
    add_audit('audit.delete_disk', disk.disk_number)
    db.session.delete(disk)
    db.session.commit()
    flash(_('flash.disk_deleted', number=disk.disk_number), 'success')
    return redirect(url_for('disks'))


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/toggle_role', methods=['POST'])
@admin_required
def toggle_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session['user_id']:
        flash(_('flash.cannot_change_own_role'), 'warning')
        return redirect(url_for('admin_users'))
    user.role = 'user' if user.role == 'admin' else 'admin'
    db.session.commit()
    role_label = _('role.admin') if user.role == 'admin' else _('role.user')
    flash(_('flash.role_updated', username=user.username, role=role_label), 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == session['user_id']:
        flash(_('flash.cannot_delete_self'), 'danger')
        return redirect(url_for('admin_users'))

    keep_data = request.form.get('keep_data') == '1'

    if keep_data:
        # 保留硬盘和数据，仅把管理人置空
        Disk.query.filter_by(manager_id=user.id).update({'manager_id': None, 'management_start': None})
        # 审计日志保留，用户字段置 NULL（外键已设 nullable）
        AuditLog.query.filter_by(user_id=user.id).update({'user_id': None})
        DiskRequest.query.filter_by(user_id=user.id).delete()
    else:
        # 删除该用户创建的数据条目
        DataEntry.query.filter_by(created_by=user.id).delete()
        # 硬盘管理权置空
        Disk.query.filter_by(manager_id=user.id).update({'manager_id': None, 'management_start': None})
        # 管理历史记录置空
        ManagementHistory.query.filter_by(manager_id=user.id).update({'manager_id': None})
        # 审计日志置空
        AuditLog.query.filter_by(user_id=user.id).update({'user_id': None})
        # 删除申请记录
        DiskRequest.query.filter_by(user_id=user.id).delete()

    action_word = _('audit.delete_user_keep') if keep_data else _('audit.delete_user_clear')
    add_audit('audit.delete_user',
              _('audit.delete_user_detail', username=user.username, action=action_word))
    db.session.delete(user)
    db.session.commit()
    flash(_('flash.user_deleted', username=user.username), 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_pw = request.form.get('new_password', '').strip()

    if len(new_pw) < 6:
        flash(_('flash.password_min_length'), 'danger')
        return redirect(url_for('admin_users'))

    user.set_password(new_pw)
    add_audit('audit.reset_password',
              _('audit.reset_password_detail', username=user.username))
    db.session.commit()
    flash(_('flash.password_reset', username=user.username), 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/audit')
@admin_required
def audit_log():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=30)
    return render_template('admin/audit.html', logs=logs)


@app.route('/admin/audit/export')
@admin_required
def export_audit():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        _('csv.audit_time'), _('csv.audit_user'), _('csv.audit_disk'),
        _('csv.audit_action'), _('csv.audit_details'),
    ])
    for log in logs:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.display_name if log.user else _('common.system'),
            log.disk.disk_number if log.disk else '',
            translate_action(log.action),
            translate_audit_details(log.action, log.details or ''),
        ])
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audit_logs.csv'}
    )


@app.route('/admin/audit/clear', methods=['POST'])
@admin_required
def clear_audit():
    count = AuditLog.query.count()
    AuditLog.query.delete()
    db.session.commit()
    flash(_('flash.audit_cleared', count=count), 'success')
    return redirect(url_for('audit_log'))


@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    display_name = request.form.get('display_name', '').strip()
    email        = request.form.get('email', '').strip()
    department   = request.form.get('department', '').strip()

    if not display_name:
        flash(_('flash.display_name_required'), 'danger')
        return redirect(url_for('admin_users'))

    user.display_name = display_name
    user.email        = email
    user.department   = department
    add_audit('audit.edit_user', _('audit.edit_user_detail', username=user.username))
    db.session.commit()
    flash(_('flash.user_updated', username=user.username), 'success')
    return redirect(url_for('admin_users'))


# ──────────────────────────────────────────────
# 用户自改密码
# ──────────────────────────────────────────────

@app.route('/profile/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = current_user()
    if request.method == 'POST':
        old_pw  = request.form.get('old_password', '')
        new_pw  = request.form.get('new_password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()

        if not user.check_password(old_pw):
            flash(_('flash.wrong_password'), 'danger')
            return render_template('change_password.html')
        if len(new_pw) < 6:
            flash(_('flash.password_min_length'), 'danger')
            return render_template('change_password.html')
        if new_pw != confirm:
            flash(_('flash.password_mismatch'), 'danger')
            return render_template('change_password.html')

        user.set_password(new_pw)
        add_audit('audit.change_password', _('audit.change_password_detail'))
        db.session.commit()
        flash(_('flash.password_changed'), 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')


# ──────────────────────────────────────────────
# 初始化数据库
# ──────────────────────────────────────────────

def migrate_db():
    """为已有数据库补充新增字段（不删数据）"""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    if 'data_entries' in tables:
        cols = {c['name'] for c in inspector.get_columns('data_entries')}
        if 'backup_location' not in cols:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(
                        'ALTER TABLE data_entries ADD COLUMN backup_location VARCHAR(512)'
                    ))
                    conn.commit()
            except Exception:
                pass

    if 'disk_requests' in tables:
        cols = {c['name'] for c in inspector.get_columns('disk_requests')}
        if 'request_type' not in cols:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE disk_requests ADD COLUMN request_type VARCHAR(20) DEFAULT 'manage'"
                    ))
                    conn.commit()
            except Exception:
                pass


def init_db():
    db.create_all()
    migrate_db()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            display_name='系统管理员',
            email='admin@hpc.local',
            department='运维部',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('[初始化] 创建默认管理员账户: admin / admin123')


# 模块加载时即初始化数据库（兼容 gunicorn 等 WSGI 服务器，不依赖 __main__）
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

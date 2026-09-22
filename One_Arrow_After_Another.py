import math
import random
import sys

import pygame

# ======================================================================
# 常量与配色
# ======================================================================
W, H = 640, 800
FPS = 60

# 方向编号
UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3
DIRS = {UP: (-1, 0), RIGHT: (0, 1), DOWN: (1, 0), LEFT: (0, -1)}
ANGLE = {UP: 270.0, RIGHT: 0.0, DOWN: 90.0, LEFT: 180.0}

# 四个方向各自的颜色，方便辨认
DIR_COLOR = {
    UP:    (86, 176, 255),
    RIGHT: (94, 214, 140),
    DOWN:  (255, 178, 84),
    LEFT:  (196, 130, 240),
}

BG_TOP = (26, 33, 54)
BG_BOT = (10, 14, 24)
CELL_COLOR = (37, 46, 70)
CELL_HOVER = (56, 70, 104)
TEXT = (228, 235, 247)
TEXT_DIM = (138, 150, 174)
ACCENT = (108, 200, 255)
DANGER = (255, 96, 96)
GOOD = (94, 214, 140)

SHAKE_TIME = 0.36       # 碰撞晃动时长（秒）
FLY_TIME = 0.35         # 飞出动画时长（秒）
MAX_MISTAKES = 3        # 每关失误上限

# 中文字体候选（找不到时界面自动回退成英文）
CJK_CANDIDATES = (
    "microsoftyahei,msyh,simhei,simsun,dengxian,"
    "notosanscjksc,notosanscjk,pingfangsc,"
    "hiraginosansgb,wenquanyimicrohei,arialunicodems"
)


# ======================================================================
# 通用小工具
# ======================================================================
def blend(c1, c2, k):
    """按比例 k 混合两色（0 → c1，1 → c2）。"""
    k = max(0.0, min(1.0, k))
    return (
        int(c1[0] + (c2[0] - c1[0]) * k),
        int(c1[1] + (c2[1] - c1[1]) * k),
        int(c1[2] + (c2[2] - c1[2]) * k),
    )


def find_font_path():
    """尝试找一个支持中文的字体文件，找不到返回 None。"""
    try:
        return pygame.font.match_font(CJK_CANDIDATES)
    except Exception:
        return None


def make_font(path, size, bold=False):
    """按字体路径创建 Font，path 为 None 时用 pygame 默认字体。"""
    if path:
        f = pygame.font.Font(path, size)
        f.set_bold(bold)
        return f
    return pygame.font.Font(None, int(size * 1.12))


def build_background():
    """预渲染竖直渐变背景，避免每帧重复计算。"""
    surf = pygame.Surface((W, H))
    for y in range(H):
        t = y / (H - 1)
        surf.fill(
            (
                int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
                int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
                int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t),
            ),
            (0, y, W, 1),
        )
    return surf


def draw_arrow_shape(surf, cx, cy, direction, size, color):
    """
    以 (cx, cy) 为中心绘制箭头。
    基础形状指向 +x（右），再按 direction 旋转。
    size 为箭头长度（像素）。
    """
    ang = math.radians(ANGLE[direction])
    ca, sa = math.cos(ang), math.sin(ang)

    base = [
        (-0.42, -0.16), (0.06, -0.16), (0.06, -0.40),
        (0.46, 0.00), (0.06, 0.40), (0.06, 0.16), (-0.42, 0.16),
    ]
    pts = []
    for x, y in base:
        rx = x * ca - y * sa
        ry = x * sa + y * ca
        pts.append((cx + rx * size, cy + ry * size))
    pygame.draw.polygon(surf, color, pts)


# ======================================================================
# 关卡：路径判定 / 可解性检测 / 生成
# ======================================================================
def path_clear(occupied, r, c, d, rows, cols):
    """
    判断 (r, c) 处朝 d 方向的箭头，到棋盘边界之间是否没有其它箭头。
    occupied 可以是 dict（以 (r, c) 为键）或 set。
    """
    dr, dc = DIRS[d]
    nr, nc = r + dr, c + dc
    while 0 <= nr < rows and 0 <= nc < cols:
        if (nr, nc) in occupied:
            return False
        nr += dr
        nc += dc
    return True


def is_solvable(grid, rows, cols):
    """
    贪心检测关卡是否可解：反复找出「当前路径畅通」的箭头并移除。
    移除箭头只会让路径更空，所以贪心顺序不影响结论。
    """
    remain = dict(grid)
    while remain:
        for key, d in list(remain.items()):
            r, c = key
            if path_clear(remain, r, c, d, rows, cols):
                del remain[key]
                break
        else:
            return False        # 还剩箭头，但一个都动不了 → 死局
    return True


def generate_solvable(rows, cols, count, rng):
    """随机生成一个保证可解的布局；生成失败则逐步减少箭头数量兜底。"""
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    count = max(1, min(count, int(rows * cols * 0.55)))
    while count >= 1:
        for _ in range(400):
            chosen = rng.sample(cells, count)
            g = {rc: rng.randrange(4) for rc in chosen}
            if is_solvable(g, rows, cols):
                return g
        count -= 1
    return {}


# ---- 手工设计并验证过的前 3 关（(行, 列): 方向） --------------------
HAND_LEVELS = [
    # ---------- 第 1 关：4x4，6 个箭头 ----------
    # 通关顺序：(0,0)↑ → (2,0)→ → (3,0)↑ → (3,3)← → (0,3)↓ → (1,1)←
    (4, 4, {
        (0, 0): UP,
        (1, 1): LEFT,
        (2, 0): RIGHT,
        (0, 3): DOWN,
        (3, 0): UP,
        (3, 3): LEFT,
    }),

    # ---------- 第 2 关：4x4，7 个箭头 ----------
    # 通关顺序：(0,0)↑ → (2,0)→ → (3,0)↑ → (3,3)← → (1,3)↓ → (0,3)↓ → (1,1)→
    (4, 4, {
        (0, 0): UP,
        (1, 1): RIGHT,
        (1, 3): DOWN,
        (2, 0): RIGHT,
        (3, 0): UP,
        (3, 3): LEFT,
        (0, 3): DOWN,
    }),

    # ---------- 第 3 关：5x5，10 个箭头 ----------
    # 通关顺序：(0,2)↓ → (2,4)↑ → (1,1)↑ → (3,3)← → (2,0)→
    #           → (0,0)→ → (4,0)↑ → (4,4)← → (1,3)↓ → (3,1)↑
    (5, 5, {
        (0, 2): DOWN,
        (2, 4): UP,
        (1, 1): UP,
        (3, 3): LEFT,
        (2, 0): RIGHT,
        (0, 0): RIGHT,
        (4, 0): UP,
        (4, 4): LEFT,
        (1, 3): DOWN,
        (3, 1): UP,
    }),
]


# ======================================================================
# 箭头对象
# ======================================================================
class Arrow:
    __slots__ = ("r", "c", "d", "state", "t", "dx", "dy", "scale")

    def __init__(self, r, c, d):
        self.r, self.c, self.d = r, c, d
        self.state = "idle"      # idle / shake / fly
        self.t = 0.0             # 动画计时
        self.dx = 0.0            # 动画像素偏移
        self.dy = 0.0
        self.scale = 1.0


# ======================================================================
# 游戏主体
# ======================================================================
class Game:
    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def __init__(self, screen):
        self.screen = screen

        # ---- 字体 ----
        self.font_path = find_font_path()
        self.cjk = self.font_path is not None     # 是否可用中文
        self.f_huge = make_font(self.font_path, 50, bold=True)
        self.f_title = make_font(self.font_path, 30, bold=True)
        self.f_hud = make_font(self.font_path, 21, bold=True)
        self.f_txt = make_font(self.font_path, 19)
        self.f_small = make_font(self.font_path, 16)

        self.bg = build_background()

        # ---- 固定 UI 矩形 ----
        self.rect_start = pygame.Rect(0, 0, 230, 62)
        self.rect_start.center = (W // 2, 600)

        self.rect_restart = pygame.Rect(W - 28 - 122, 24, 122, 40)

        self.rect_next = pygame.Rect(0, 0, 230, 58)
        self.rect_next.center = (W // 2, H // 2 + 96)

        # ---- 状态 ----
        self.scene = "start"          # start / game / win / lose
        self.level = 1
        self.anim = 0.0
        self.overlay_t = 0.0

        self.load_level(1)

    # ------------------------------------------------------------------
    # 文案（有中文字体用中文，否则用英文）
    # ------------------------------------------------------------------
    def T(self, zh, en):
        return zh if self.cjk else en

    # ------------------------------------------------------------------
    # 关卡装载
    # ------------------------------------------------------------------
    def load_level(self, n):
        """装载第 n 关，重置失误次数与所有动画状态。"""
        self.level = n

        if 1 <= n <= len(HAND_LEVELS):
            rows, cols, data = HAND_LEVELS[n - 1]
        else:
            idx = n - len(HAND_LEVELS) - 1
            rows = min(4 + idx // 2, 7)
            cols = rows
            count = min(6 + idx, rows * cols - 3)
            rng = random.Random(9000 + n)          # 固定种子 → 每次重开一致
            data = generate_solvable(rows, cols, count, rng)

        self.rows, self.cols = rows, cols
        self.max_mistakes = MAX_MISTAKES
        self.mistakes = 0

        self.grid = {rc: Arrow(rc[0], rc[1], d) for rc, d in data.items()}
        self.flying = []                            # 正在飞出的箭头
        self.overlay_t = 0.0

        self.compute_layout()

    def restart_level(self):
        """把当前关卡恢复到初始状态。"""
        self.load_level(self.level)

    def compute_layout(self):
        """根据棋盘大小计算格子尺寸与棋盘左上角位置。"""
        board_top, board_bottom = 130, H - 80
        avail_w = W - 64
        avail_h = board_bottom - board_top

        cell = min(avail_w // self.cols, avail_h // self.rows, 116)
        self.cell = cell

        bw, bh = cell * self.cols, cell * self.rows
        self.ox = (W - bw) // 2
        self.oy = board_top + (avail_h - bh) // 2

    # ------------------------------------------------------------------
    # 坐标换算
    # ------------------------------------------------------------------
    def cell_at(self, pos):
        """屏幕坐标 → 网格坐标；不在棋盘内返回 None。"""
        mx, my = pos
        if not (self.ox <= mx < self.ox + self.cell * self.cols):
            return None
        if not (self.oy <= my < self.oy + self.cell * self.rows):
            return None
        return (int((my - self.oy) // self.cell),
                int((mx - self.ox) // self.cell))

    def cell_center(self, r, c):
        return (self.ox + c * self.cell + self.cell / 2,
                self.oy + r * self.cell + self.cell / 2)

    # ------------------------------------------------------------------
    # 输入
    # ------------------------------------------------------------------
    def on_click(self, pos):
        if self.scene == "start":
            if self.rect_start.collidepoint(pos):
                self.load_level(1)
                self.scene = "game"
            return

        if self.scene == "game":
            if self.rect_restart.collidepoint(pos):
                self.restart_level()
                return
            self.click_board(pos)
            return

        # 通关 / 失败界面
        if self.overlay_t > 0.30 and self.rect_next.collidepoint(pos):
            if self.scene == "win":
                self.load_level(self.level + 1)
            else:
                self.restart_level()
            self.scene = "game"

    def click_board(self, pos):
        """处理一次棋盘点击。"""
        if self.scene != "game":
            return

        cell = self.cell_at(pos)
        if cell is None:
            return

        arrow = self.grid.get(cell)
        if arrow is None or arrow.state != "idle":
            return

        if path_clear(self.grid, arrow.r, arrow.c, arrow.d,
                      self.rows, self.cols):
            # ---- 前方无阻挡：飞出棋盘 ----
            del self.grid[cell]
            arrow.state = "fly"
            arrow.t = 0.0
            self.flying.append(arrow)
        else:
            # ---- 前方有阻挡：晃动提示 + 记一次失误 ----
            arrow.state = "shake"
            arrow.t = 0.0
            self.mistakes += 1
            if self.mistakes >= self.max_mistakes:
                self.scene = "lose"
                self.overlay_t = 0.0

    def on_key(self, key):
        if key == pygame.K_r and self.scene == "game":
            self.restart_level()
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.scene == "win" and self.overlay_t > 0.30:
                self.load_level(self.level + 1)
                self.scene = "game"
            elif self.scene == "lose" and self.overlay_t > 0.30:
                self.restart_level()
                self.scene = "game"
            elif self.scene == "start":
                self.load_level(1)
                self.scene = "game"

    # ------------------------------------------------------------------
    # 每帧更新
    # ------------------------------------------------------------------
    def update(self, dt):
        self.anim += dt
        self.overlay_t += dt

        # 被挡住 → 左右晃动
        for a in self.grid.values():
            if a.state == "shake":
                a.t += dt
                if a.t >= SHAKE_TIME:
                    a.state = "idle"
                    a.t = 0.0
                    a.dx = 0.0
                else:
                    k = 1.0 - a.t / SHAKE_TIME
                    a.dx = math.sin(a.t * 62.0) * 9.0 * k

        # 飞出的箭头
        for a in self.flying[:]:
            a.t += dt
            p = min(a.t / FLY_TIME, 1.0)
            e = p * p * (3 - 2 * p)                 # smoothstep 缓动
            dr, dc = DIRS[a.d]
            dist = (self.rows + self.cols + 1) * self.cell
            a.dx = dc * dist * e
            a.dy = dr * dist * e
            a.scale = 1.0 - 0.5 * p
            if p >= 1.0:
                self.flying.remove(a)

        # 胜利判定
        if self.scene == "game" and not self.grid and not self.flying:
            self.scene = "win"
            self.overlay_t = 0.0

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def draw(self):
        if self.scene == "start":
            self.draw_start()
            return

        self.screen.blit(self.bg, (0, 0))
        self.draw_hud()
        self.draw_board()

        if self.scene in ("win", "lose"):
            self.draw_overlay()

    # ---------------- 开始界面 ----------------
    def draw_start(self):
        self.screen.blit(self.bg, (0, 0))

        # 标题
        img = self.f_huge.render(self.T("一箭又一箭", "ONE ARROW AFTER ANOTHER"),
                                 True, TEXT)
        self.screen.blit(img, img.get_rect(center=(W // 2, 168)))

        img = self.f_txt.render(
            self.T("点击箭头，让它飞出去", "Click an arrow to shoot it out"),
            True, TEXT_DIM)
        self.screen.blit(img, img.get_rect(center=(W // 2, 228)))

        # 四个方向的装饰箭头
        for i, d in enumerate((UP, RIGHT, DOWN, LEFT)):
            draw_arrow_shape(self.screen, W // 2 - 150 + i * 100, 320,
                             d, 46, DIR_COLOR[d])

        # 玩法说明
        lines = [
            self.T("· 点击箭头，箭头沿所指方向前进",
                   "Click an arrow: it moves forward"),
            self.T("· 前方没有其它箭头 → 飞出棋盘并消失",
                   "No arrow ahead -> flies off the board"),
            self.T("· 前方有箭头阻挡 → 无法消除，消耗 1 次失误",
                   "Blocked -> cannot leave, costs 1 miss"),
            self.T("· 清空全部箭头过关；失误用尽则失败",
                   "Clear all arrows to win; no misses left = lose"),
        ]
        y = 400
        for ln in lines:
            img = self.f_txt.render(ln, True, TEXT)
            self.screen.blit(img, img.get_rect(center=(W // 2, y)))
            y += 40

        self.draw_button(self.rect_start, self.T("开始游戏", "START"))

    # ---------------- 游戏界面 HUD ----------------
    def draw_hud(self):
        # 当前关卡
        img = self.f_hud.render(self.T(f"第 {self.level} 关", f"Level {self.level}"),
                                True, ACCENT)
        self.screen.blit(img, (28, 30))

        # 重新开始按钮
        self.draw_button(self.rect_restart, self.T("重新开始", "RESTART"),
                         primary=False)

        # 剩余箭头数量
        n = len(self.grid)
        img = self.f_txt.render(self.T(f"剩余箭头：{n}", f"Arrows left: {n}"),
                                True, TEXT)
        self.screen.blit(img, (28, 82))

        # 剩余失误次数（用圆点表示）
        label = self.f_txt.render(self.T("失误", "Misses"), True, TEXT_DIM)
        gap, dotr = 26, 9
        total = label.get_width() + 12 + gap * self.max_mistakes
        x0 = W - 28 - total
        self.screen.blit(label, (x0, 82))
        cy = 82 + label.get_height() // 2
        for i in range(self.max_mistakes):
            cx = x0 + label.get_width() + 12 + gap // 2 + i * gap
            if i < self.mistakes:
                pygame.draw.circle(self.screen, DANGER, (cx, cy), dotr)
            else:
                pygame.draw.circle(self.screen, (60, 70, 96), (cx, cy), dotr)

        # 底部操作提示
        img = self.f_small.render(
            self.T("点击箭头射击 · R 重开本关 · Esc 退出",
                   "Click to shoot - R restart - Esc quit"),
            True, TEXT_DIM)
        self.screen.blit(img, img.get_rect(center=(W // 2, H - 38)))

    # ---------------- 棋盘 ----------------
    def draw_board(self):
        cell = self.cell
        pad = 10

        board = pygame.Rect(self.ox - pad, self.oy - pad,
                            cell * self.cols + pad * 2,
                            cell * self.rows + pad * 2)
        pygame.draw.rect(self.screen, (16, 21, 34), board, border_radius=20)
        pygame.draw.rect(self.screen, (44, 55, 80), board, 2, border_radius=20)

        hover = self.cell_at(pygame.mouse.get_pos()) if self.scene == "game" else None

        # 格子底色
        for r in range(self.rows):
            for c in range(self.cols):
                rect = pygame.Rect(self.ox + c * cell + 5,
                                   self.oy + r * cell + 5,
                                   cell - 10, cell - 10)
                col = CELL_HOVER if (r, c) == hover else CELL_COLOR
                pygame.draw.rect(self.screen, col, rect, border_radius=10)

        # 盘面上的箭头 + 正在飞出的箭头
        for a in self.grid.values():
            self.draw_arrow(a)
        for a in self.flying:
            self.draw_arrow(a)

    def draw_arrow(self, a):
        cx, cy = self.cell_center(a.r, a.c)
        cx += a.dx
        cy += a.dy
        size = self.cell * 0.66 * a.scale

        col = DIR_COLOR[a.d]
        if a.state == "shake":
            # 越接近结束越红，形成明显的碰撞反馈
            k = max(0.0, 1.0 - a.t / SHAKE_TIME)
            col = blend(col, DANGER, 0.85 * k)

        draw_arrow_shape(self.screen, cx, cy, a.d, size, col)

    # ---------------- 通关 / 失败界面 ----------------
    def draw_overlay(self):
        if self.overlay_t < 0.20:
            return

        alpha = min(215, int(215 * (self.overlay_t - 0.20) / 0.30))
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 10, 18, alpha))
        self.screen.blit(veil, (0, 0))

        if self.scene == "win":
            title = self.T("过关！", "LEVEL CLEAR!")
            col = GOOD
            sub = self.T(f"第 {self.level} 关完成", f"Level {self.level} cleared")
            btn = self.T("下一关", "NEXT")
        else:
            title = self.T("失误用尽", "OUT OF MISSES")
            col = DANGER
            sub = self.T("本关失败", "Level failed")
            btn = self.T("重新开始", "RETRY")

        img = self.f_huge.render(title, True, col)
        self.screen.blit(img, img.get_rect(center=(W // 2, H // 2 - 80)))

        img = self.f_txt.render(sub, True, TEXT)
        self.screen.blit(img, img.get_rect(center=(W // 2, H // 2 - 16)))

        self.draw_button(self.rect_next, btn)

    # ---------------- 按钮 ----------------
    def draw_button(self, rect, text, primary=True):
        hovered = rect.collidepoint(pygame.mouse.get_pos())

        if primary:
            base, fg = ACCENT, (10, 16, 26)
        else:
            base, fg = (54, 66, 94), TEXT

        col = blend(base, (255, 255, 255), 0.16 if hovered else 0.0)
        pygame.draw.rect(self.screen, col, rect, border_radius=12)
        if not primary:
            pygame.draw.rect(self.screen, (80, 95, 130), rect, 2, border_radius=12)

        img = self.f_hud.render(text, True, fg)
        self.screen.blit(img, img.get_rect(center=rect.center))


# ======================================================================
# 程序入口
# ======================================================================
def main():
    pygame.init()
    pygame.display.set_caption("一箭又一箭 / One Arrow After Another")
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    game = Game(screen)

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
                game.on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.on_click(event.pos)

        game.update(dt)
        game.draw()
        pygame.display.flip()


if __name__ == "__main__":
    main()
           
from gi.repository import Gtk
from threading import Timer
import cairo

class Base(Gtk.DrawingArea):
    steps = 3

    def __init__(self):
        super(Base, self).__init__()
        self.width = 96
        self.height = 48

        self.set_size_request(self.width, self.height)
        self.style = self.get_style_context()

        self.connect("draw", self.draw)

        self.timer = None
        self.state = -2.
        self.duration = 50

    def draw(self, widget, ctx):
        x = self.width / 2.
        y = self.height / 2.

        if self.state < 0:
            self.preview(ctx, x, y)
        else:
            self.animation(ctx, x, y)

    def preview(self, ctx, x, y):
        self.window(ctx, x, y, x, y)

    def animation(self, ctx, x, y):
        self.window(ctx, x, y, x, y)

    def window(self, ctx, x, y, w, h, alpha=1, scale=1):
        if scale <= 0:
            return
        alpha = min(max(alpha, 0), 1)

        c = self.get_color()
        ctx.set_source_rgba(c.red, c.green, c.blue, alpha)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(scale, scale)

        ctx.rectangle(-w / 2, -h / 2, w, h)
        ctx.fill()
        ctx.restore()

    def get_color(self):
        if self.state == -2:
            return self.style.get_background_color(Gtk.StateFlags.SELECTED)
        return self.style.get_color(Gtk.StateFlags.NORMAL)

    def start(self, a, b):
        if self.state == -2:
            self.state = -1.
            self.queue_draw()
            self.timer = Timer(.5, self.frame)
            self.timer.start()

    def stop(self, a, b):
        self.state = -2.
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        self.queue_draw()

    def frame(self):
        self.state += 1
        if self.state <= self.duration:
            self.queue_draw()
            self.timer = Timer(.01, self.frame)
            self.timer.start()
        elif self.timer is not None:
            self.timer.cancel()
            self.state = self.duration

class BaseMax(Base):
    def preview(self, ctx, x, y):
        self.window(ctx, x, y, x * 2, y * 2)

    def animation(self, ctx, x, y):
        self.window(ctx, x, y, x * 2, y * 2)


class ScaleIn(Base):
    def preview(self, ctx, x, y):
        for i in range(self.steps):
            self.window(ctx, x, y, x, y, (self.steps - i) * 1. / self.steps, (i + 1.) / self.steps)

    def animation(self, ctx, x, y):
        scale = self.transition(self.state, 0, 1, self.duration)
        self.window(ctx, x, y, x, y, scale=scale)

class ScaleOut(ScaleIn):
    def animation(self, ctx, x, y):
        scale = self.transition(self.state, 1, -1, self.duration)
        self.window(ctx, x, y, x, y, scale=scale)

class ScaleMax(Base):
    def preview(self, ctx, x, y):
        for i in range(self.steps + 1):
            i *= 1.
            self.window(ctx, x, y, x, y, (self.steps - i + 1) / (self.steps + 1), i / self.steps + 1)

    def animation(self, ctx, x, y):
        scale = self.transition(self.state, 1, 1, self.duration)
        self.window(ctx, x, y, x, y, scale=scale)

class ScaleUnMax(ScaleMax):
    def animation(self, ctx, x, y):
        scale = self.transition(self.state, 2, -1, self.duration)
        self.window(ctx, x, y, x, y, scale=scale)


class FadeIn(Base):
    def preview(self, ctx, x, y):
        self.window(ctx, x, y, x, y, .5)

    def animation(self, ctx, x, y):
        alpha = self.transition(self.state, 0, 1, self.duration)
        self.window(ctx, x, y, x, y, alpha)

class FadeOut(FadeIn):
    def animation(self, ctx, x, y):
        alpha = self.transition(self.state, 1, -1, self.duration)
        self.window(ctx, x, y, x, y, alpha)


class MoveIn(Base):
    def preview(self, ctx, x, y):
        gradient = cairo.LinearGradient(x / 5, y / 5, x, y)
        c = self.get_color()
        gradient.add_color_stop_rgba(0, c.red, c.green, c.blue, 0)
        gradient.add_color_stop_rgb(1, c.red, c.green, c.blue)
        ctx.set_source(gradient)
        ctx.move_to(x / 5, y / 5)
        ctx.line_to(x * 1.5, y * .5)
        ctx.line_to(x * 1.5, y * 1.5)
        ctx.line_to(x * .5, y * 1.5)
        ctx.fill()

    def animation(self, ctx, x, y):
        d = self.transition(self.state, .2, .8, self.duration)
        scale = self.transition(self.state, 0, 1, self.duration)
        self.window(ctx, x * d, y * d, x, y, scale=scale)

class MoveOut(MoveIn):
    def animation(self, ctx, x, y):
        d = self.transition(self.state, 1, -.8, self.duration)
        scale = self.transition(self.state, 1, -1, self.duration)
        self.window(ctx, x * d, y * d, x, y, scale=scale)

class Traditional(Base):
    def preview(self, ctx, x, y):
        gradient = cairo.LinearGradient(x, y * 2, x, y)
        c = self.get_color()
        gradient.add_color_stop_rgba(0, c.red, c.green, c.blue, 0)
        gradient.add_color_stop_rgb(1, c.red, c.green, c.blue)
        ctx.set_source(gradient)
        ctx.move_to(x, y * 2)
        ctx.line_to(x * 1.5, y * 1.5)
        ctx.line_to(x * 1.5, y * .5)
        ctx.line_to(x * .5, y * .5)
        ctx.line_to(x * .5, y * 1.5)
        ctx.fill()

    def animation(self, ctx, x, y):
        d = self.transition(self.state, 1, 1, self.duration)
        scale = self.transition(self.state, 1, -1, self.duration)
        self.window(ctx, x, y * d, x, y, scale=scale)


class FlyUpIn(Base):
    def preview(self, ctx, x, y):
        gradient = cairo.LinearGradient(0, y * 2, 0, y * 1.5)
        c = self.get_color()
        gradient.add_color_stop_rgba(0, c.red, c.green, c.blue, 0)
        gradient.add_color_stop_rgb(1, c.red, c.green, c.blue)
        ctx.set_source(gradient)
        ctx.rectangle(x / 2, y / 2, x, y * 1.5)
        ctx.fill()

    def animation(self, ctx, x, y):
        d = self.transition(self.state, y * 2.5, y * -1.5, self.duration)
        self.window(ctx, x, d, x, y)

class FlyUpOut(Base):
    def preview(self, ctx, x, y):
        gradient = cairo.LinearGradient(0, 0, 0, y / 2)
        c = self.get_color()
        gradient.add_color_stop_rgba(0, c.red, c.green, c.blue, 0)
        gradient.add_color_stop_rgb(1, c.red, c.green, c.blue)
        ctx.set_source(gradient)
        ctx.rectangle(x / 2, 0, x, y * 1.5)
        ctx.fill()

    def animation(self, ctx, x, y):
        d = self.transition(self.state, y, y * -1.5, self.duration)
        self.window(ctx, x, d, x, y)


class FlyDownIn(FlyUpOut):
    def animation(self, ctx, x, y):
        d = self.transition(self.state, y * -.5, y * 1.5, self.duration)
        self.window(ctx, x, d, x, y)

class FlyDownOut(FlyUpIn):
    def animation(self, ctx, x, y):
        d = self.transition(self.state, y, y * 1.5, self.duration)
        self.window(ctx, x, d, x, y)



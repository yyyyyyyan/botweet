from threading import Event, Thread


class BotweetEvent(Event):
    def __init__(self, func, *args, **kwargs):
        super(BotweetEvent, self).__init__()
        kwargs["stop_event"] = self
        self.thread = Thread(target=func, args=args, kwargs=kwargs)
        self.thread.start()

    def stop(self):
        self.set()
        self.thread.join()

    @property
    def stopped(self):
        return self.is_set()

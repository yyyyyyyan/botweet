from threading import Event

class BotweetEvent(Event):
    def __init__(self):
        super(BotweetEvent, self).__init__()

    def stop(self):
        self.set()

    @property
    def stopped(self):
        return self.is_set()


class ExtraContextMixin(object):

    """ Add extra context to a View
    :param extra_context:
        Dictionary containing variables which are added to the template
        context.
     """


    extra_context = None

    def get_context_data(self, *args, **kwargs):
        context = super(ExtraContextMixin, self).get_context_data(*args, **kwargs)
        if self.extra_context:
            context.update(self.extra_context)
        return context

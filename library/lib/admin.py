from django.contrib import admin
from .models import Book, Category, Reader, Issue, Fine

admin.site.register(Book)
admin.site.register(Category)
admin.site.register(Reader)
admin.site.register(Issue)
admin.site.register(Fine)

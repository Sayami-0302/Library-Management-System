from django.urls import path
from . import views
urlpatterns=[
    path('', views.home, name='home'),
    path('features/', views.features_page, name='features'),
    path('about/', views.about_page, name='about'),
    path('contact/', views.contact_page, name='contact'),
    path('add_book/', views.add_book, name='add_book'),
    path('books/', views.view_books, name='view_books'),
    path('admin/books/<int:pk>/', views.admin_book_details, name='admin_book_details'),
    path('books/edit/<int:pk>/', views.edit_book, name='edit_book'),
    path('books/delete/<int:pk>/', views.delete_book, name='delete_book'),
    # path('books/search/', views.search_books, name='search_books'),
    path('books/<int:pk>/', views.book_details, name='book_details'), #by using primary key
    path('books/<int:pk>/description/', views.book_description, name='book_description'),
    # path('books/<str:isbn>/', views.book_details, name='book_details'), # for isbn 
    path('all-books/', views.public_books, name='public_books'),#home page ko lagi



    #reader urls
    path('readers/', views.view_readers, name='view_readers'),
    #path('readers/add/', views.add_reader, name='add_reader'),
    path('reader/books/<int:pk>/', views.reader_book_detail, name='reader_book_detail'),
    path('reader/books/<int:pk>/rate/', views.rate_book, name='rate_book'),
    path('readers/<int:pk>/edit/', views.edit_reader, name='edit_reader'),
    path('readers/<int:pk>/delete/', views.delete_reader, name='delete_reader'),
    path('readers/<int:pk>/', views.reader_details, name='reader_details'),

    # issue related
    path('issues/add/', views.issue_book, name='issue_book'),
    path('issues/import/', views.import_issues, name='import_issues'),
    path('issues/', views.view_issues, name='view_issues'),
    path('issues/<int:pk>/return/', views.return_book, name='return_book'),
    path('issues/overdue/', views.overdue_books, name='overdue_books'),
    #fine related
    path('fines/', views.view_fines, name='view_fines'),
    path('fines/<int:pk>/pay/', views.pay_fine, name='pay_fine'),
    #register and login for reader
    path('readers/register/', views.register_reader, name='register_reader'),
    path('readers/login/', views.login_reader, name='login_reader'),
    path('readers/logout/', views.logout_reader, name='logout_reader'),
    path('reader/settings/change-password/', views.reader_change_password, name='reader_change_password'),
    path('reader/settings/delete-account/', views.reader_delete_account, name='reader_delete_account'),
    path('reader/books/', views.reader_view_books, name='reader_view_books'),
    path('readers/dashboard/', views.reader_dashboard, name='reader_dashboard'),
    path('readers/profile/', views.reader_profile, name='reader_profile'),
    path('readers/profile/edit/', views.edit_reader_profile, name='edit_reader_profile'),
    path('reader/books/<int:book_id>/request/', views.issue_request, name='issue_request'),
    path('reader/issued/', views.reader_issued_books, name='reader_issued_books'),
    path('reader/notifications/', views.reader_notifications, name='reader_notifications'),
    path('reader/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    ## admin
    path('admin/register/', views.register_admin, name='register_admin'),
    path('admin/login/', views.login_admin, name='login_admin'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/profile/', views.admin_profile, name='admin_profile'),
    path('admin/profile/edit/', views.edit_admin_profile, name='edit_admin_profile'),
    path('admin/settings/change-password/', views.admin_change_password, name='admin_change_password'),
    path('admin/settings/delete-account/', views.admin_delete_account, name='admin_delete_account'),
    path('admin/logout/', views.logout_admin, name='logout_admin'),
    path('admin/issue-requests/', views.admin_issue_requests, name='admin_issue_requests'),
    path('admin/issue-requests/<int:request_id>/approve/', views.approve_request, name='approve_request'),
    path('admin/issue-requests/<int:request_id>/reject/', views.reject_request, name='reject_request'),
    path('admin/issue-requests/bulk/', views.bulk_update_requests, name='bulk_update_requests'),

    #category related
    path('admin/categories/', views.view_categories, name='view_categories'),
    path('admin/categories/add/', views.add_category, name='add_category'),
    path('admin/categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('admin/categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),

    # bulk + import
    path('admin/books/import/', views.import_books, name='import_books'),
    path('admin/books/bulk-update/', views.bulk_update_books, name='bulk_update_books'),
    #search book
    path('ajax/search-books/', views.ajax_search_books, name='ajax_search_books'),
    #analytics
    path('books/<int:pk>/analytics/', views.book_analytics_api, name='book_analytics_api'),
    
    # export functionality
    path('issues/export/', views.export_issues, name='export_issues'),
    path('fines/export/', views.export_fines, name='export_fines'),
    path('readers/export/', views.export_readers, name='export_readers'),
]
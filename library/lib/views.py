from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .forms import BookForm,ReaderForm,IssueForm,ReaderRegisterForm
from .models import Book,Reader,Issue,Fine,IssueRequest,Admin,Category,Notification,BookIssuanceRecord, BookRating
from django.db.models import Q, Count, Avg, Case, When, Value, F, IntegerField
from django.utils import timezone
from django.utils.timezone import now
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta,date
from django.contrib import messages
from django.urls import reverse
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from .forms import UploadExcelForm
from .models import Book, Category
import json
import csv
import io
from functools import wraps
from django.conf import settings
from django.core.paginator import Paginator

# maximum number of books a reader can have at once (including pending requests)
MAX_ISSUED_PER_READER = getattr(settings, 'MAX_ISSUED_PER_READER', 5)


def paginate_queryset(request, queryset, per_page=20):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def pagination_querystring(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def admin_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return redirect('login_admin')
        try:
            admin = Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            request.session.pop('admin_id', None)
            request.session.pop('is_superuser', None)
            return redirect('login_admin')
        if not admin.is_active:
            messages.error(request, "Your admin account is inactive. Please contact the superuser.")
            request.session.pop('admin_id', None)
            request.session.pop('is_superuser', None)
            return redirect('login_admin')
        request.admin_user = admin
        return view_func(request, *args, **kwargs)
    return _wrapped


def superuser_required(view_func):
    @wraps(view_func)
    def inner(request, *args, **kwargs):
        admin = getattr(request, 'admin_user', None)
        if not admin or not admin.is_superuser:
            messages.error(request, "Superuser privileges are required for that action.")
            return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)
    return admin_login_required(inner)


def get_logged_in_reader(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return None
    try:
        return Reader.objects.get(id=reader_id)
    except Reader.DoesNotExist:
        request.session.pop('reader_id', None)
        return None
def home(request):
    categories = Category.objects.all()
    # show a small selection of books on the homepage (e.g., latest or popular)
    books = Book.objects.all().order_by('-id')[:6]
    return render(request, 'landing.html', {
        'year': now().year,
        'categories': categories,
        'books': books,
    })


def features_page(request):
    return render(request, 'features.html')


def about_page(request):
    return render(request, 'about.html')


def contact_page(request):
    return render(request, 'contact.html')

def public_books(request):
    # Accept optional query and category filters via GET
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    books = Book.objects.all()
    if q:
        # Search across name, author, ISBN only (NOT category)
        books = books.filter(
            Q(name__icontains=q) |
            Q(author__icontains=q) |
            Q(isbn__icontains=q)
        ).annotate(
            # Prioritize: book name that starts with query first (so "A" shows "Atomic Habits" before others),
            # then name contains, then author, ISBN.
            match_priority=Case(
                When(name__istartswith=q, then=Value(0)),
                When(name__icontains=q, then=Value(1)),
                When(author__istartswith=q, then=Value(2)),
                When(author__icontains=q, then=Value(3)),
                When(isbn__istartswith=q, then=Value(4)),
                When(isbn__icontains=q, then=Value(5)),
                default=Value(6),
                output_field=IntegerField()
            )
        ).order_by('match_priority', 'name')
    else:
        books = books.order_by('name')  # sorted alphabetically
    
    # Category filter (separate from search)
    if category_id:
        try:
            cid = int(category_id)
            books = books.filter(category_id=cid)
        except ValueError:
            pass

    categories = Category.objects.all()
    page_obj = paginate_queryset(request, books, 20)
    return render(request, 'public_books.html', {
        'books': page_obj,
        'page_obj': page_obj,
        'categories': categories,
        'query': q,
        'selected_category': category_id,
        'pagination_query': pagination_querystring(request),
        'current_page': 'public_books',
    })


@admin_login_required
def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('view_books')  # redirect to view_books after adding
    else:
        form = BookForm()
    return render(request, 'add_book.html', {'form': form})


@admin_login_required
def edit_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return redirect('view_books')
    else:
        form = BookForm(instance=book)
    return render(request, 'edit_book.html', {'form': form})

@admin_login_required
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        return redirect('view_books')
    return render(request, 'delete_book.html', {'book': book})



@admin_login_required
def view_books(request):
    """
    Display all books in the library with advanced filters.
    """
    books = Book.objects.select_related('category').all()
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    if q:
        books = books.filter(
            Q(name__icontains=q) |
            Q(author__icontains=q) |
            Q(isbn__icontains=q) |
            Q(category__name__icontains=q)
        )
    if category_id:
        try:
            cid = int(category_id)
            books = books.filter(category_id=cid)
        except ValueError:
            pass

    books = books.order_by('name')
    page_obj = paginate_queryset(request, books, 20)
    context = {
        'books': page_obj,
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'pagination_query': pagination_querystring(request),
        'query': q,
        'selected_category': category_id,
    }
    return render(request, 'view_books.html', context)



def book_details(request, pk):
    # Render different detail pages depending on who is viewing:
    # - Admins: show admin_book_details.html (with admin controls)
    # - Logged-in reader: show reader_book_detail.html (reader-specific layout)
    # - Anonymous/general visitor: show public book_details.html

    # If admin session exists, reuse admin_book_details view
    if request.session.get('admin_id'):
        return admin_book_details(request, pk)

    # If reader session exists, reuse reader_book_detail view
    if request.session.get('reader_id'):
        return reader_book_detail(request, pk)

    # General visitor (not admin and not logged-in reader)
    book = get_object_or_404(Book, pk=pk)  # fetch book or return 404 if not found
    analytics = get_book_analytics_data(book, days=90)
    popular_books = get_popular_books(limit=3, exclude_book_id=pk)
    return render(request, 'book_details.html', {
        'book': book,
        'analytics': analytics,
        'popular_books': popular_books,
    })


def book_description(request, pk):
    """Render a simple page that shows the book title and its full description.

    This can be used for a dedicated description view or AJAX-loaded fragment.
    """
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'book_description.html', {'book': book})


def admin_book_details(request, pk):
    """Admin-only book details view. Requires admin session; otherwise redirects to admin login."""
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    book = get_object_or_404(Book, pk=pk)
    analytics = get_book_analytics_data(book, days=90)
    popular_books = get_popular_books(limit=3, exclude_book_id=pk)
    return render(request, 'admin_book_details.html', {
        'book': book,
        'analytics': analytics,
        'popular_books': popular_books,
    })



### reader views

def add_reader(request):
    if request.method == 'POST':
        form = ReaderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('view_readers')  # will make this view later
    else:
        form = ReaderForm()
    return render(request, 'add_reader.html', {'form': form})

def view_readers(request):
    readers = Reader.objects.all().order_by('name')
    page_obj = paginate_queryset(request, readers, 20)
    return render(request, 'view_readers.html', {
        'readers': page_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_querystring(request),
    })


@admin_login_required
def toggle_reader_active(request, pk):
    # Currently not exposed in the UI; kept for potential future use.
    reader = get_object_or_404(Reader, pk=pk)
    reader.is_active = not reader.is_active
    reader.save()
    messages.success(request, f"Reader '{reader.name}' has been {'activated' if reader.is_active else 'deactivated'}.")
    return redirect('view_readers')


@admin_login_required
def reset_reader_password(request, pk):
    # Currently not exposed in the UI; kept for potential future use.
    reader = get_object_or_404(Reader, pk=pk)
    reader.password = 'temp123'
    reader.save()
    messages.success(request, f"Password for '{reader.name}' has been reset to a temporary value.")
    return redirect('view_readers')


def edit_reader(request, pk):
    reader = get_object_or_404(Reader, pk=pk)
    if request.method == 'POST':
        form = ReaderForm(request.POST, instance=reader)
        if form.is_valid():
            form.save()
            return redirect('view_readers')
    else:
        form = ReaderForm(instance=reader)
    return render(request, 'edit_reader.html', {'form': form, 'reader': reader})

def delete_reader(request, pk):
    reader = get_object_or_404(Reader, pk=pk)
    if request.method == 'POST':
        reader.delete()
        return redirect('view_readers')
    return render(request, 'delete_reader.html', {'reader': reader})

def reader_details(request, pk):
    reader = get_object_or_404(Reader, pk=pk)
    issues = reader.issues.all()  # uses related_name='issues' from Issue model
    return render(request, 'reader_details.html', {'reader': reader, 'issues': issues})

###  Issue or borrow related
@admin_login_required
def issue_book(request):
    if request.method == 'POST':
        form = IssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)

            #  Prevent duplicate issue: same reader + same book + not returned
            if Issue.objects.filter(reader=issue.reader, book=issue.book, returned_date__isnull=True).exists():
                form.add_error('book', f"{issue.reader.name} already has '{issue.book.name}' issued.")
            else:
                #  automatically set issued_date if not provided
                if not issue.issued_date:
                    issue.issued_date = date.today()

                #  validate due_date
                if not issue.due_date:
                    # If the reader is marked as staff_member, give 6 months (approx 182 days), else default 14 days
                    if getattr(issue.reader, 'is_staff_member', False):
                        issue.due_date = issue.issued_date + timedelta(days=182)
                    else:
                        issue.due_date = issue.issued_date + timedelta(days=14)  # default 2 weeks
                elif issue.due_date <= issue.issued_date:
                    form.add_error('due_date', 'Due date must be after today.')
                elif issue.due_date > issue.issued_date + timedelta(days=30):
                    form.add_error('due_date', 'Due date cannot exceed 30 days from today.')

                # proceed if no due_date errors
                if not form.errors:
                    if issue.book.number_in_stock > 0:
                        issue.book.number_in_stock -= 1
                        issue.book.save()
                        issue.save()
                        messages.success(request, f"'{issue.book.name}' issued to {issue.reader.name}.")
                        return redirect('view_issues')
                    else:
                        form.add_error('book', 'This book is out of stock!')
    else:
        form = IssueForm()

    return render(request, 'issue_book.html', {'form': form})



@admin_login_required
def view_issues(request):
    issues = Issue.objects.all().order_by('-issued_date')  # latest first
    page_obj = paginate_queryset(request, issues, 20)
    today = timezone.now().date()
    for issue in page_obj:
        issue.is_overdue = (not issue.returned_date) and issue.due_date and issue.due_date < today
    return render(request, 'view_issues.html', {
        'issues': page_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_querystring(request),
    })

@admin_login_required
def return_book(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    
    if request.method == 'POST':
        if not issue.returned_date:  # only if not already returned
            issue.returned_date = timezone.now().date()
            issue.book.number_in_stock += 1  # increase book stock
            issue.book.save()
            issue.save()
        return redirect('view_issues')
    
    return render(request, 'return_book.html', {'issue': issue})

@admin_login_required
def overdue_books(request):
    today = timezone.now().date()
    overdue_issues = Issue.objects.filter(returned_date__isnull=True, due_date__lt=today).select_related('reader', 'book').order_by('due_date')
    
    # Calculate days overdue for each issue
    for issue in overdue_issues:
        issue.days_overdue = (today - issue.due_date).days

    return render(request, 'overdue_books.html', {'overdue_issues': overdue_issues})
### for fines
@admin_login_required
def view_fines(request):
    fines = Fine.objects.select_related('issue__reader', 'issue__book').all().order_by('-calculated_date')
    page_obj = paginate_queryset(request, fines, 20)
    return render(request, 'view_fines.html', {
        'fines': page_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_querystring(request),
    })

@admin_login_required
def pay_fine(request, pk):
    fine = get_object_or_404(Fine, pk=pk)
    if request.method == 'POST':
        fine.paid = True
        fine.save()
        return redirect('view_fines')
    return render(request, 'pay_fine.html', {'fine': fine})

## register  for reader


def register_reader(request):
    if request.method == 'POST':
        form = ReaderRegisterForm(request.POST)
        if form.is_valid():
            reader = form.save(commit=False)
            # Store password as plain text for simplicity (consider hashing in future)
            password = form.cleaned_data.get('password')
            if password:
                reader.password = password
            # ensure is_staff_member is set (form provides it)
            reader.is_staff_member = form.cleaned_data.get('is_staff_member', False)
            reader.save()
            return redirect('login_reader')
    else:
        form = ReaderRegisterForm()
    return render(request, 'register_reader.html', {'form': form})

# login for reader
def login_reader(request):
    error = None
    if request.method == 'POST':
        reader_id = request.POST.get('reader_id')
        password = request.POST.get('password')
        try:
            reader = Reader.objects.get(reader_id=reader_id, password=password)
            request.session['reader_id'] = reader.id  # store session
            # Cache staff flag in session for quick checks in templates/views
            request.session['is_staff_member'] = bool(getattr(reader, 'is_staff_member', False))
            return redirect('reader_dashboard')  # you can create a dashboard view
        except Reader.DoesNotExist:
            error = "Invalid Reader ID or password"
    return render(request, 'login_reader.html', {'error': error})

def logout_reader(request):
    if 'reader_id' in request.session:
        del request.session['reader_id']
    if 'is_staff_member' in request.session:
        del request.session['is_staff_member']
    return redirect('home')


def reader_change_password(request):
    reader = get_logged_in_reader(request)
    if not reader:
        return redirect('login_reader')
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1 = request.POST.get('new_password', '')
        new2 = request.POST.get('confirm_password', '')
        if current != (reader.password or ''):
            messages.error(request, "Current password is incorrect.")
        elif not new1 or new1 != new2:
            messages.error(request, "New passwords do not match.")
        else:
            reader.password = new1
            reader.save()
            messages.success(request, "Password updated successfully.")
            return redirect('reader_dashboard')
    return render(request, 'reader_change_password.html', {'reader': reader})


def reader_delete_account(request):
    reader = get_logged_in_reader(request)
    if not reader:
        return redirect('login_reader')
    if request.method == 'POST':
        # Block deletion if there are any unreturned books
        has_unreturned = Issue.objects.filter(reader=reader, returned_date__isnull=True).exists()
        if has_unreturned:
            messages.error(request, 'Account cannot be deleted until all borrowed books are returned.')
            return redirect('reader_delete_account')

        reader.delete()
        request.session.pop('reader_id', None)
        request.session.pop('is_staff_member', None)
        return redirect('home')
    return render(request, 'reader_delete_account.html', {'reader': reader})


# reader dashboard
def reader_dashboard(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')  # redirect if not logged in

    reader = Reader.objects.get(id=reader_id)

    # All books issued to this reader
    issues = reader.issues.all().order_by('-issued_date')  # uses related_name='issues'

    # Calculate fines for overdue books if not already created
    today = timezone.now().date()
    for issue in issues:
        if not issue.returned_date and issue.due_date < today:
            # Create fine if it doesn't exist
            fine, created = Fine.objects.get_or_create(issue=issue, defaults={
                'amount': (today - issue.due_date).days * 2  # example: $2 per overdue day
            })
    
    # Check and create notifications for due soon and overdue books
    check_and_create_due_soon_notifications()
    check_and_create_overdue_notifications()
    
    fines = Fine.objects.filter(issue__reader=reader, paid=False)
    unread_notif_count = reader.notifications.filter(read=False).count()

    return render(request, 'reader_dashboard.html', {
        'reader': reader,
        'issues': issues,
        'fines': fines,
        'unread_notif_count': unread_notif_count,
    })

def reader_profile(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')
    
    try:
        reader = Reader.objects.get(id=reader_id)
    except Reader.DoesNotExist:
        return redirect('login_reader')
    
    unread_notif_count = reader.notifications.filter(read=False).count()
    
    return render(request, 'reader_profile.html', {
        'reader': reader,
        'unread_notif_count': unread_notif_count,
    })

def edit_reader_profile(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')
    
    try:
        reader = Reader.objects.get(id=reader_id)
    except Reader.DoesNotExist:
        return redirect('login_reader')
    
    if request.method == 'POST':
        from .forms import ReaderEditProfileForm
        form = ReaderEditProfileForm(request.POST, request.FILES, instance=reader)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('reader_profile')
    else:
        from .forms import ReaderEditProfileForm
        form = ReaderEditProfileForm(instance=reader)
    
    unread_notif_count = reader.notifications.filter(read=False).count()
    
    return render(request, 'edit_reader_profile.html', {
        'form': form,
        'reader': reader,
        'unread_notif_count': unread_notif_count,
    })

def reader_view_books(request):
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    books = Book.objects.select_related('category').all()
    if q:
        books = books.filter(
            Q(name__icontains=q) |
            Q(author__icontains=q) |
            Q(isbn__icontains=q) |
            Q(category__name__icontains=q)
        )
    if category_id:
        try:
            cid = int(category_id)
            books = books.filter(category_id=cid)
        except ValueError:
            pass

    books = books.order_by('name')
    page_obj = paginate_queryset(request, books, 20)
    return render(request, 'books.html', {
        'books': page_obj,
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'pagination_query': pagination_querystring(request),
        'query': q,
        'selected_category': category_id,
        'current_page': 'reader_view_books',
    })

def reader_book_detail(request, pk):
    """
    View for a reader to see book details.
    """
    book = get_object_or_404(Book, pk=pk)
    analytics = get_book_analytics_data(book, days=90)
    popular_books = get_popular_books(limit=3, exclude_book_id=pk)
    # compute average rating given by readers
    avg_reader_rating = BookRating.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg']
    if avg_reader_rating is None:
        avg_reader_rating = float(book.rating)
    else:
        avg_reader_rating = float(avg_reader_rating)

    combined_rating = round((float(book.rating) + avg_reader_rating) / 2.0, 1)

    # current user's rating (if logged in)
    user_rating = None
    reader_obj = None
    reader_id = request.session.get('reader_id')
    if reader_id:
        reader_obj = Reader.objects.filter(id=reader_id).first()
        if reader_obj:
            ur = BookRating.objects.filter(book=book, reader=reader_obj).first()
            if ur:
                user_rating = float(ur.rating)

    return render(request, 'reader_book_detail.html', {
        'book': book,
        'analytics': analytics,
        'popular_books': popular_books,
        'combined_rating': combined_rating,
        'avg_reader_rating': round(avg_reader_rating, 1),
        'user_rating': user_rating,
    })


def rate_book(request, pk):
    """AJAX endpoint for readers to submit/update a rating for a book."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    reader_id = request.session.get('reader_id')
    if not reader_id:
        return JsonResponse({'error': 'login required'}, status=403)

    reader = get_object_or_404(Reader, id=reader_id)
    book = get_object_or_404(Book, pk=pk)

    try:
        rating = float(request.POST.get('rating', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'invalid rating'}, status=400)

    if rating < 1 or rating > 5:
        return JsonResponse({'error': 'rating out of range (1-5)'}, status=400)

    br, created = BookRating.objects.update_or_create(
        book=book,
        reader=reader,
        defaults={'rating': rating}
    )

    avg_reader = BookRating.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg'] or float(book.rating)
    avg_reader = float(avg_reader)
    combined = round((float(book.rating) + avg_reader) / 2.0, 1)

    return JsonResponse({
        'combined_rating': combined,
        'avg_reader_rating': round(avg_reader, 1),
        'user_rating': float(br.rating),
    })

def issue_request(request, book_id):
    # Check if reader is logged in
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')  # redirect if not logged in

    reader = get_object_or_404(Reader, id=reader_id)
    book = get_object_or_404(Book, id=book_id)

    # Enforce per-reader limit: current issued books + pending requests must be < MAX
    current_issued = Issue.objects.filter(reader=reader, returned_date__isnull=True).count()
    current_pending = IssueRequest.objects.filter(reader=reader, approved=False, rejected=False).count()
    if current_issued + current_pending >= MAX_ISSUED_PER_READER:
        messages.error(request, (
            f"You cannot request more books. You already have {current_issued} issued and {current_pending} pending "
            f"(limit is {MAX_ISSUED_PER_READER}). Return a book or cancel a pending request first."
        ))
        return redirect('reader_view_books')

    # ✅ Restrict duplicate issued books
    if Issue.objects.filter(reader=reader, book=book, returned_date__isnull=True).exists():
        messages.error(request, f"You already have '{book.name}' issued.")
        return redirect('reader_view_books')

    # ✅ Prevent duplicate pending requests
    if IssueRequest.objects.filter(reader=reader, book=book, approved=False, rejected=False).exists():
        messages.warning(request, f"You already have a pending request for '{book.name}'.")
        return redirect('reader_view_books')

    # ✅ Create new request
    IssueRequest.objects.create(reader=reader, book=book)
    messages.success(request, f"Issue request for '{book.name}' submitted successfully!")

    return redirect('reader_view_books')

def reader_issued_books(request):
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')

    reader = Reader.objects.get(id=reader_id)
    issued_books = Issue.objects.filter(reader=reader).order_by('-issued_date')
    page_obj = paginate_queryset(request, issued_books, 20)

    return render(request, 'reader_issued_books.html', {
        'reader': reader,
        'issued_books': page_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_querystring(request),
    })


### admin
def register_admin(request):
    from .forms import AdminRegisterForm
    superuser_exists = Admin.objects.filter(is_superuser=True).exists()
    requester = None
    if superuser_exists:
        admin_id = request.session.get('admin_id')
        if not admin_id:
            messages.error(request, "Only the superuser can create new admin accounts.")
            return redirect('login_admin')
        requester = Admin.objects.filter(id=admin_id).first()
        if not requester or not requester.is_superuser or not requester.is_active:
            messages.error(request, "Only the superuser can create new admin accounts.")
            return redirect('admin_dashboard')

    if request.method == 'POST':
        form = AdminRegisterForm(request.POST)
        if form.is_valid():
            active_admins = Admin.objects.filter(is_superuser=False, is_active=True).count()
            if superuser_exists and active_admins >= 5:
                form.add_error(None, "Cannot create more than five active admin accounts.")
            else:
                admin = form.save(commit=False)
                admin.password = make_password(form.cleaned_data['password'])
                # First admin becomes superuser by default
                admin.is_superuser = not superuser_exists
                admin.is_active = True
                admin.save()
                if not superuser_exists:
                    messages.success(request, "Superuser account created. Please log in.")
                else:
                    messages.success(request, "Admin account created successfully.")
                return redirect('login_admin')
    else:
        form = AdminRegisterForm()
    return render(request, 'register_admin.html', {'form': form})

# Admin Login
def login_admin(request):
    error = None
    if request.method == 'POST':
        admin_id = request.POST.get('admin_id')
        password = request.POST.get('password')
        try:
            admin = Admin.objects.get(admin_id=admin_id)
            if not admin.is_active:
                error = "This admin account is inactive. Please contact the superuser."
            elif check_password(password, admin.password):
                request.session['admin_id'] = admin.id
                request.session['is_superuser'] = admin.is_superuser
                return redirect('admin_dashboard')
            else:
                error = "Invalid Admin ID or password"
        except Admin.DoesNotExist:
            error = "Invalid Admin ID or password"
    return render(request, 'login_admin.html', {'error': error})

# Admin Dashboard
@admin_login_required
def admin_dashboard(request):
    admin = request.admin_user
    total_books = Book.objects.count()
    total_readers = Reader.objects.count()
    low_stock_books = Book.objects.filter(number_in_stock__lte=1).order_by('number_in_stock', 'name')[:8]

    return render(request, 'admin_dashboard.html', {
        'admin': admin,
        'total_books': total_books,
        'total_readers': total_readers,
        'low_stock_books': low_stock_books,
    })

@admin_login_required
def admin_profile(request):
    admin = request.admin_user
    return render(request, 'admin_profile.html', {
        'admin': admin,
    })

@admin_login_required
def edit_admin_profile(request):
    admin = request.admin_user
    
    if request.method == 'POST':
        from .forms import AdminEditProfileForm
        form = AdminEditProfileForm(request.POST, request.FILES, instance=admin)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('admin_profile')
    else:
        from .forms import AdminEditProfileForm
        form = AdminEditProfileForm(instance=admin)
    
    return render(request, 'edit_admin_profile.html', {
        'form': form,
        'admin': admin,
    })

@admin_login_required
def admin_change_password(request):
    admin = request.admin_user
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1 = request.POST.get('new_password', '')
        new2 = request.POST.get('confirm_password', '')
        if not check_password(current, admin.password):
            messages.error(request, "Current password is incorrect.")
        elif not new1 or new1 != new2:
            messages.error(request, "New passwords do not match.")
        else:
            admin.password = make_password(new1)
            admin.save()
            messages.success(request, "Password updated successfully.")
            return redirect('admin_dashboard')
    return render(request, 'admin_change_password.html', {'admin': admin})
# Admin Logout
def logout_admin(request):
    request.session.pop('admin_id', None)
    request.session.pop('is_superuser', None)
    return redirect('home')


@admin_login_required
def admin_delete_account(request):
    admin = request.admin_user
    if request.method == 'POST':
        if admin.is_superuser:
            messages.error(request, "Superuser account cannot be deleted from here.")
            return redirect('admin_dashboard')
        name = admin.name
        admin.delete()
        request.session.pop('admin_id', None)
        request.session.pop('is_superuser', None)
        messages.success(request, f"Account '{name}' has been deleted.")
        return redirect('home')
    return render(request, 'admin_delete_account.html', {'admin': admin})


# View all pending requests
@admin_login_required
def admin_issue_requests(request):
    pending_requests = IssueRequest.objects.filter(approved=False, rejected=False).order_by('request_date')
    return render(request, 'admin_issue_requests.html', {'pending_requests': pending_requests})


@admin_login_required
def approve_request(request, request_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    req = get_object_or_404(IssueRequest, pk=request_id, approved=False, rejected=False)
    book = req.book
    reader = req.reader
    # Enforce per-reader limit: count currently issued books and pending requests
    current_issued = Issue.objects.filter(reader=reader, returned_date__isnull=True).count()
    current_pending = IssueRequest.objects.filter(reader=reader, approved=False, rejected=False).count()
    total_count = current_issued + current_pending

    # If total already exceeds the allowed maximum, reject approval
    if total_count > MAX_ISSUED_PER_READER:
        messages.error(request, (
            f"Cannot approve request: {reader.name} already has {total_count} books/pending requests, "
            f"which exceeds the limit of {MAX_ISSUED_PER_READER}."
        ))
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    #  Check if reader already has this book issued
    if Issue.objects.filter(reader=reader, book=book, returned_date__isnull=True).exists():
        messages.error(request, f"{reader.name} already has '{book.name}' issued.")
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    #  Check stock availability
    if book.number_in_stock <= 0:
        messages.error(request, f"No copies of '{book.name}' are available.")
        req.rejected = True
        req.save()
        return redirect('admin_issue_requests')

    #  Approve request and issue the book
    # compute due_date depending on whether the reader is a staff member
    issued_date = date.today()
    if getattr(reader, 'is_staff_member', False):
        due = issued_date + timedelta(days=182)  # ~6 months
    else:
        due = issued_date + timedelta(days=14)

    issue = Issue.objects.create(
        reader=reader,
        book=book,
        issued_date=issued_date,
        due_date=due
    )
    book.number_in_stock -= 1
    book.save()

    # Create a notification for the issued book
    create_issue_notification(issue)
    
    # Record issuance for analytics
    record_book_issuance(book, issued_date=issue.issued_date)

    req.approved = True
    req.save()

    messages.success(request, f"Issue request approved: '{book.name}' issued to {reader.name}.")
    return redirect('admin_issue_requests')

@admin_login_required
def reject_request(request, request_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    req = get_object_or_404(IssueRequest, pk=request_id, approved=False, rejected=False)
    req.rejected = True
    req.save()

    # Create a notification for the reader informing them their request was rejected
    try:
        Notification.objects.create(
            reader=req.reader,
            issue=None,
            notification_type='request_rejected',
            title=f"Request Rejected: {req.book.name}",
            message=f"Your request to issue '{req.book.name}' was rejected by the library administrator."
        )
    except Exception:
        # If notification creation fails for any reason, continue silently but log to console for debugging
        print(f"Failed to create rejection notification for IssueRequest {req.pk}")

    return redirect('admin_issue_requests')

#category for admin

@admin_login_required
def view_categories(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    categories = Category.objects.all().order_by('name')
    page_obj = paginate_queryset(request, categories, 20)
    return render(request, 'admin_view_categories.html', {
        'categories': page_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_querystring(request),
    })

# Add new category
@admin_login_required
def add_category(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Category.objects.create(name=name)
            return redirect('view_categories')

    return render(request, 'admin_add_category.html')

# Edit category
@admin_login_required
def edit_category(request, category_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            category.name = name
            category.save()
            return redirect('view_categories')

    return render(request, 'admin_edit_category.html', {'category': category})

# Delete category
@admin_login_required
def delete_category(request, category_id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login_admin')

    category = get_object_or_404(Category, id=category_id)
    category.delete()
    return redirect('view_categories')


@admin_login_required
def bulk_update_requests(request):
    if request.method != 'POST':
        return redirect('admin_issue_requests')

    action = request.POST.get('action')
    ids = request.POST.getlist('request_ids')
    if not ids or action not in ('approve', 'reject'):
        messages.error(request, 'Please select at least one request and an action.')
        return redirect('admin_issue_requests')

    for rid in ids:
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            continue
        if action == 'approve':
            approve_request(request, rid_int)
        else:
            reject_request(request, rid_int)

    return redirect('admin_issue_requests')


@admin_login_required
def bulk_update_books(request):
    if request.method != 'POST':
        return redirect('view_books')

    ids = request.POST.getlist('book_ids')
    category_id = request.POST.get('category_id') or ''
    status = request.POST.get('status') or ''

    if not ids:
        messages.error(request, 'No books selected for bulk update.')
        return redirect('view_books')

    qs = Book.objects.filter(id__in=ids)
    updates = {}

    if category_id:
        try:
            cid = int(category_id)
            category = Category.objects.get(id=cid)
            updates['category'] = category
        except (ValueError, Category.DoesNotExist):
            pass
    if status and status in dict(Book.STATUS_CHOICES):
        updates['status'] = status

    if updates:
        qs.update(**updates)
        messages.success(request, f'Updated {qs.count()} book(s).')
    else:
        messages.info(request, 'Nothing to update; category/status left unchanged.')

    return redirect('view_books')


@admin_login_required
def import_issues(request):
    """
    Import multiple issued-book records from a CSV file.

    Expected columns (header row required):
      - reader_id  (required)  -> Reader.reader_id
      - isbn       (required)  -> Book.isbn
      - issued_date (optional, YYYY-MM-DD). Defaults to today if blank.
      - due_date    (optional, YYYY-MM-DD). If blank, computed using same rules
                     as the single-issue form: staff ~6 months, others 14 days.
    """
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded = request.FILES['file']
        try:
            raw = uploaded.read()
            try:
                text = raw.decode('utf-8-sig')
            except AttributeError:
                text = raw
            reader_csv = csv.DictReader(io.StringIO(text))
            created = 0
            skipped = 0
            errors = 0

            for row in reader_csv:
                try:
                    reader_code = (row.get('reader_id') or '').strip()
                    isbn = (row.get('isbn') or '').strip()
                    issued_str = (row.get('issued_date') or '').strip()
                    due_str = (row.get('due_date') or '').strip()

                    if not reader_code or not isbn:
                        skipped += 1
                        continue

                    # Look up reader and book
                    try:
                        reader = Reader.objects.get(reader_id=reader_code)
                    except Reader.DoesNotExist:
                        errors += 1
                        continue
                    try:
                        book = Book.objects.get(isbn=isbn)
                    except Book.DoesNotExist:
                        errors += 1
                        continue

                    # Prevent duplicate active issue
                    if Issue.objects.filter(reader=reader, book=book, returned_date__isnull=True).exists():
                        skipped += 1
                        continue

                    # Check stock
                    if book.number_in_stock <= 0:
                        errors += 1
                        continue

                    # Dates
                    issued_date = None
                    if issued_str:
                        try:
                            issued_date = date.fromisoformat(issued_str)
                        except ValueError:
                            errors += 1
                            continue
                    else:
                        issued_date = date.today()

                    if due_str:
                        try:
                            due_date = date.fromisoformat(due_str)
                        except ValueError:
                            errors += 1
                            continue
                    else:
                        if getattr(reader, 'is_staff_member', False):
                            due_date = issued_date + timedelta(days=182)
                        else:
                            due_date = issued_date + timedelta(days=14)

                    Issue.objects.create(
                        reader=reader,
                        book=book,
                        issued_date=issued_date,
                        due_date=due_date
                    )
                    book.number_in_stock -= 1
                    book.save()
                    created += 1
                except Exception:
                    errors += 1
                    continue

            if created:
                messages.success(request, f'Imported {created} issue(s) from CSV.')
            if skipped:
                messages.info(request, f'Skipped {skipped} row(s) (duplicates or missing required fields).')
            if errors:
                messages.error(request, f'{errors} row(s) failed due to invalid data.')

        except Exception as e:
            messages.error(request, f'Failed to import issues CSV: {e}')

        return redirect('view_issues')

    return render(request, 'issue_book.html', {'form': IssueForm()})

### Searching books


def ajax_search_books(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    try:
        limit = int(request.GET.get('limit', '8'))
    except (ValueError, TypeError):
        limit = 8

    books = Book.objects.all()
    # Search across book name, author, and ISBN only (NOT category)
    if query:
        books = books.filter(
            Q(name__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query)
        ).annotate(
            # Prioritize: book name starts with query (0) > name contains (1) >
            # author starts with (2) > author contains (3) > ISBN
            match_priority=Case(
                When(name__istartswith=query, then=Value(0)),
                When(name__icontains=query, then=Value(1)),
                When(author__istartswith=query, then=Value(2)),
                When(author__icontains=query, then=Value(3)),
                When(isbn__istartswith=query, then=Value(4)),
                When(isbn__icontains=query, then=Value(5)),
                default=Value(6),
                output_field=IntegerField()
            )
        ).order_by('match_priority', 'name')
    else:
        books = books.order_by('name')
    
    # Category filter (separate from search - for filtering only)
    if category_id:
        books = books.filter(category_id=category_id)

    # Apply limit for performance
    books = books[:limit]

    data = []
    for book in books:
        # Choose correct detail URL depending on who is viewing
        if request.session.get('admin_id'):
            url = reverse('admin_book_details', args=[book.pk])  # admin book detail
        elif request.session.get('reader_id'):
            url = reverse('reader_book_detail', args=[book.pk])  # logged-in reader detail
        else:
            url = reverse('book_details', args=[book.pk])  # public/detail view for anonymous users

        # Debug print
        print(f"User: {request.user}, is_staff: {getattr(request.user, 'is_staff', False)}, Book URL: {url}")

        # compute reader average and combined rating for this book
        try:
            avg_reader = BookRating.objects.filter(book=book).aggregate(avg=Avg('rating'))['avg'] or float(book.rating)
            avg_reader = float(avg_reader)
        except Exception:
            avg_reader = float(book.rating)
        combined = round((float(book.rating) + avg_reader) / 2.0, 1)
        # include a short description snippet if available
        desc = ''
        try:
            desc = (book.description or '')[:180]
        except Exception:
            desc = ''

        data.append({
            'name': book.name,
            'author': book.author,
            'isbn': getattr(book, 'isbn', ''),
            'category': book.category.name if book.category else '',
            'category_id': book.category.id if book.category else '',
            'image': book.image.url if getattr(book, 'image', None) else '',
            'pk': book.pk,
            'url': url,
            'stock': book.number_in_stock,
            'avg_reader_rating': round(avg_reader, 1),
            'combined_rating': combined,
            'description': desc,
        })

    return JsonResponse({'books': data})



# (Removed commented-out example rate_book handler — ratings implemented elsewhere)


### Notification system

def create_issue_notification(issue):
    """Create a notification when a book is issued to a reader."""
    Notification.objects.create(
        reader=issue.reader,
        issue=issue,
        notification_type='issued',
        title=f"Book Issued: {issue.book.name}",
        message=f"You have been issued '{issue.book.name}' by {issue.book.author}. Due date: {issue.due_date}"
    )


def check_and_create_due_soon_notifications():
    """Create notifications for books due in 2 days. Call this periodically (e.g., via cron/celery)."""
    today = timezone.now().date()
    target_date = today + timedelta(days=2)
    
    # Find issues that are due in 2 days and not yet notified
    issues = Issue.objects.filter(
        due_date=target_date,
        returned_date__isnull=True
    ).select_related('reader', 'book')
    
    for issue in issues:
        # Check if notification already exists for this issue
        if not Notification.objects.filter(issue=issue, notification_type='due_soon').exists():
            Notification.objects.create(
                reader=issue.reader,
                issue=issue,
                notification_type='due_soon',
                title=f"Due Soon: {issue.book.name}",
                message=f"'{issue.book.name}' is due on {issue.due_date}. Please return it on time to avoid fines."
            )


def check_and_create_overdue_notifications():
    """Create notifications for overdue books. Call this periodically (e.g., via cron/celery)."""
    today = timezone.now().date()
    
    # Find overdue issues (not returned and due date passed) and not yet notified
    overdue_issues = Issue.objects.filter(
        due_date__lt=today,
        returned_date__isnull=True
    ).select_related('reader', 'book')
    
    for issue in overdue_issues:
        # Check if notification already exists for this issue
        if not Notification.objects.filter(issue=issue, notification_type='overdue').exists():
            days_overdue = (today - issue.due_date).days
            Notification.objects.create(
                reader=issue.reader,
                issue=issue,
                notification_type='overdue',
                title=f"Overdue: {issue.book.name}",
                message=f"'{issue.book.name}' is {days_overdue} day(s) overdue. Please return it immediately to avoid additional fines."
            )


def reader_notifications(request):
    """Display all notifications for the logged-in reader."""
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')
    
    reader = Reader.objects.get(id=reader_id)
    notifications = reader.notifications.all()
    unread_count = notifications.filter(read=False).count()
    
    # Mark as read if requested
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        if notification_id:
            notif = get_object_or_404(Notification, id=notification_id, reader=reader)
            notif.read = True
            notif.save()
            return redirect('reader_notifications')
    
    return render(request, 'reader_notifications.html', {
        'reader': reader,
        'notifications': notifications,
        'unread_count': unread_count,
    })


def mark_all_notifications_read(request):
    """Mark all notifications as read for the logged-in reader."""
    reader_id = request.session.get('reader_id')
    if not reader_id:
        return redirect('login_reader')
    
    reader = Reader.objects.get(id=reader_id)
    reader.notifications.filter(read=False).update(read=True)
    
    return redirect('reader_notifications')


### Analytics

def record_book_issuance(book, issued_date=None):
    """Record a book issuance in the analytics."""
    if issued_date is None:
        issued_date = date.today()
    
    record, created = BookIssuanceRecord.objects.get_or_create(
        book=book,
        date=issued_date,
        defaults={'quantity_issued': 0}
    )
    record.quantity_issued += 1
    record.save()


def get_book_analytics_data(book, days=90):
    """Get analytics data for a book over the last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    records = BookIssuanceRecord.objects.filter(
        book=book,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    dates = [str(r.date) for r in records]
    quantities = [r.quantity_issued for r in records]
    
    return {
        'dates': dates,
        'quantities': quantities,
        'total_issued': sum(quantities),
        'avg_per_day': sum(quantities) / max(len(records), 1) if records else 0,
    }


def book_analytics_api(request, pk):
    """API endpoint to return analytics data as JSON."""
    book = get_object_or_404(Book, pk=pk)
    days = request.GET.get('days', 90)
    
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 90
    
    data = get_book_analytics_data(book, days=days)
    return JsonResponse(data)


def get_popular_books(limit=3, exclude_book_id=None):
    """Get random popular books with rating > 4.5."""
    books = Book.objects.filter(rating__gt=4.5)
    
    if exclude_book_id:
        books = books.exclude(pk=exclude_book_id)
    
    # Order by random and limit
    books = books.order_by('?')[:limit]
    return books
@admin_login_required
def import_books(request):
    if request.method == "POST":
        form = UploadExcelForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']

            try:
                df = pd.read_excel(excel_file)
            except Exception as e:
                messages.error(request, f"Error reading Excel: {e}")
                return redirect("import_books")

            required_columns = [
                "name",
                "isbn",
                "author",
                "category",
                "number_in_stock",
                "description",
                "rating",
                "status",
            ]

            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                messages.error(request, f"Missing required columns: {', '.join(missing)}")
                return redirect("import_books")

            created = 0
            updated = 0

            with transaction.atomic():
                for idx, row in df.iterrows():

                    category_name = row.get("category")
                    category_obj = None
                    if category_name and str(category_name).strip():
                        category_obj, _ = Category.objects.get_or_create(
                            name=str(category_name).strip()
                        )

                    book, was_created = Book.objects.update_or_create(
                        isbn=str(row["isbn"]).strip(),
                        defaults={
                            "name": row["name"],
                            "author": row["author"],
                            "category": category_obj,
                            "number_in_stock": int(row["number_in_stock"] or 0),
                            "description": row.get("description") or "No description available",
                            "rating": float(row.get("rating") or 4.0),
                            "status": str(row.get("status") or "available").lower(),
                        }
                    )

                    created += int(was_created)
                    updated += int(not was_created)

            messages.success(request, f"Books Imported Successfully! Created: {created}, Updated: {updated}")
            return redirect("import_books")

    else:
        form = UploadExcelForm()

    return render(request, "import_books.html", {"form": form})


### Export Functions

@admin_login_required
def export_issues(request):
    """Export issues data in different formats"""
    format_type = request.GET.get('format', 'csv').lower()
    
    # Get all issues
    issues = Issue.objects.select_related('reader', 'book').all().order_by('-issued_date')
    
    # Create data list
    data = []
    for issue in issues:
        data.append({
            'Reader Name': issue.reader.name,
            'Reader ID': issue.reader.reader_id,
            'Book Name': issue.book.name,
            'ISBN': issue.book.isbn,
            'Issued Date': issue.issued_date,
            'Due Date': issue.due_date,
            'Returned Date': issue.returned_date or 'Not Returned',
            'Status': 'Returned' if issue.returned_date else 'Not Returned',
        })
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="issues.csv"'
        
        writer = csv.DictWriter(response, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        return response
    
    elif format_type == 'xlsx':
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="issues.xlsx"'
        
        with io.BytesIO() as buffer:
            df.to_excel(buffer, index=False)
            response.write(buffer.getvalue())
        return response
    
    elif format_type == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib import colors
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="issues.pdf"'
            
            doc = SimpleDocTemplate(response, pagesize=A4)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("Issues Report", styles['Title'])
            elements.append(title)
            
            # Table data
            table_data = [['Reader Name', 'Reader ID', 'Book Name', 'ISBN', 'Issued Date', 'Due Date', 'Returned Date', 'Status']]
            for item in data:
                table_data.append([
                    item['Reader Name'],
                    item['Reader ID'],
                    item['Book Name'],
                    item['ISBN'],
                    str(item['Issued Date']),
                    str(item['Due Date']),
                    str(item['Returned Date']),
                    item['Status'],
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            
            doc.build(elements)
            return response
        except ImportError:
            messages.error(request, "PDF export requires reportlab library.")
            return redirect('view_issues')
    
    messages.error(request, "Invalid format specified.")
    return redirect('view_issues')


@admin_login_required
def export_fines(request):
    """Export fines data in different formats"""
    format_type = request.GET.get('format', 'csv').lower()
    
    # Get all fines
    fines = Fine.objects.select_related('issue__reader', 'issue__book').all().order_by('-calculated_date')
    
    # Create data list
    data = []
    for fine in fines:
        data.append({
            'Reader Name': fine.issue.reader.name,
            'Reader ID': fine.issue.reader.reader_id,
            'Book Name': fine.issue.book.name,
            'Amount': float(fine.amount),
            'Calculated Date': fine.calculated_date,
            'Status': 'Paid' if fine.paid else 'Unpaid',
        })
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="fines.csv"'
        
        writer = csv.DictWriter(response, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        return response
    
    elif format_type == 'xlsx':
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="fines.xlsx"'
        
        with io.BytesIO() as buffer:
            df.to_excel(buffer, index=False)
            response.write(buffer.getvalue())
        return response
    
    elif format_type == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib import colors
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="fines.pdf"'
            
            doc = SimpleDocTemplate(response, pagesize=A4)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("Fines Report", styles['Title'])
            elements.append(title)
            
            # Table data
            table_data = [['Reader Name', 'Reader ID', 'Book Name', 'Amount', 'Calculated Date', 'Status']]
            for item in data:
                table_data.append([
                    item['Reader Name'],
                    item['Reader ID'],
                    item['Book Name'],
                    f"₹{item['Amount']}",
                    str(item['Calculated Date']),
                    item['Status'],
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            
            doc.build(elements)
            return response
        except ImportError:
            messages.error(request, "PDF export requires reportlab library.")
            return redirect('view_fines')
    
    messages.error(request, "Invalid format specified.")
    return redirect('view_fines')


@admin_login_required
def export_readers(request):
    """Export readers data in different formats"""
    format_type = request.GET.get('format', 'csv').lower()
    
    # Get all readers
    readers = Reader.objects.all().order_by('name')
    
    # Create data list
    data = []
    for reader in readers:
        data.append({
            'Reader ID': reader.reader_id,
            'Name': reader.name,
            'Date of Birth': reader.date_of_birth,
            'Phone': reader.phone_number,
            'Address': reader.address,
            'Status': 'Active' if reader.is_active else 'Inactive',
            'Role': 'Staff/Teacher' if reader.is_staff_member else 'Student',
        })
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="readers.csv"'
        
        writer = csv.DictWriter(response, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        return response
    
    elif format_type == 'xlsx':
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="readers.xlsx"'
        
        with io.BytesIO() as buffer:
            df.to_excel(buffer, index=False)
            response.write(buffer.getvalue())
        return response
    
    elif format_type == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib import colors
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="readers.pdf"'
            
            doc = SimpleDocTemplate(response, pagesize=A4)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("Readers Report", styles['Title'])
            elements.append(title)
            
            # Table data
            table_data = [['Reader ID', 'Name', 'Date of Birth', 'Phone', 'Address', 'Status', 'Role']]
            for item in data:
                table_data.append([
                    item['Reader ID'],
                    item['Name'],
                    str(item['Date of Birth']),
                    item['Phone'],
                    item['Address'][:20] + '...' if len(item['Address']) > 20 else item['Address'],
                    item['Status'],
                    item['Role'],
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            
            doc.build(elements)
            return response
        except ImportError:
            messages.error(request, "PDF export requires reportlab library.")
            return redirect('view_readers')
    
    messages.error(request, "Invalid format specified.")
    return redirect('view_readers')


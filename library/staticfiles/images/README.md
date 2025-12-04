Place the homepage image (provided as an attachment) here and name it `library_home.jpg`.

Path to save the file:

library/static/images/library_home.jpg

After copying the image to that path, the home page will show the image below the welcome card.

Example command (from project root `LMS/library`):

# if the attachment is saved in your Downloads folder as 'home_photo.jpg'
# adjust filename accordingly
cp ~/Downloads/home_photo.jpg static/images/library_home.jpg

If you're using git, add and commit the file if you want it versioned:

git add static/images/library_home.jpg
git commit -m "Add homepage image"

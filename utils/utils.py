from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.response import Response
from orders.models import OrderProduct, Order
from users.utils.email_async import run_async


@run_async
def send_email(
    subject,
    email,
    recipient_list,
    context,
    template_url: str = "email/newsletter-subscription.html",
    success_message: str = "Email sent successfully",
):
    """
    Prepares and sends an HTML email to a given recipient.

    Args:
        subject (str): The subject line of the email.
        email (str): The recipient's email address.
        recipient_list (list): Not used in this function. (Consider removing if unnecessary).
        context (dict): Context data to render the email template.
        template_url (str, optional): Path to the HTML template used for the email body. Defaults to 'email/newsletter-subscription.html'.
        success_message (str, optional): Message returned in the response upon successful email delivery. Defaults to 'Email sent successfully'.

    Returns:
        Response: A DRF Response object indicating success or failure with an appropriate message.
    """
    html_content = render_to_string(template_url, context)
    text_content = strip_tags(html_content)

    try:
        email_msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=f"no-reply@{settings.SITE_URL}",
            to=[email],
        )
        email_msg.attach_alternative(html_content, "text/html")
        email_msg.send()

        return Response({"message": success_message}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Failed to send email: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def update_product_score(product, rating):
    """
    Updates the score of a product based on a given rating.

    Rules:
    - If the current score is 0 and the rating is less than 4, set the score to 1.
    - If the rating is greater than 3, increment the score by 1.
    - If the rating is 3 or less (and not caught by the first rule), decrement the score by 1.
    - The score will not go below 0.

    Args:
        product: The product instance whose score will be updated.
        rating (int): The rating value (e.g., from a user).

    Returns:
        None
    """
    if product.score == 0 and rating < 4:
        product.score = 1
    elif rating > 3:
        product.score += 1
    else:
        product.score = max(product.score - 1, 0)

    product.save()



def update_bestseller_status(product, threshold=20):
    """
    Calculates the total quantity sold of a given product (excluding 'PENDING' orders),
    and updates its 'best_seller' status if it meets or fails to meet the defined threshold.

    Args:
        product (Product): The product instance to evaluate.
        threshold (int, optional): The sales threshold to be considered a bestseller. Defaults to 1000.

    Behavior:
        - Counts the total quantity of this product in non-'PENDING' orders.
        - Sets 'best_seller' to True if total sales >= threshold.
        - Sets 'best_seller' to False if total sales < threshold.
        - Saves the product only if the status changes.

    Returns:
        None
    """

    total_sales = (
        OrderProduct.objects.filter(
            product=product,
            order__status__iexact="PROCESSING",  # or use ~Q(order__status="PENDING") to exclude
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    if total_sales >= threshold and not product.best_seller:
        product.best_seller = True
        product.save()
    elif total_sales < threshold and product.best_seller:
        product.best_seller = False
        product.save()




def is_first_purchase(user) -> bool:
    """
    Determines if the user is making their first purchase.

    Args:
        user (User): The user instance to check.

    Returns:
        bool: True if the user has no previous orders (i.e., this is their first purchase),
              False otherwise.
    """
    return not Order.objects.filter(user=user).exists()

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary using a key.
    Useful for keys with spaces or special characters.
    
    Usage in template:
        {{ my_dict|get_item:"key with spaces" }}
        
    Example:
        {{ leaves_stats|get_item:"Pending Approval"|default:"0" }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0
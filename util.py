# System imports

# ResumeNet imports


class Direction(object):
    """Defines the direction in ring."""

    RIGHT = 0

    LEFT = not RIGHT

    @staticmethod
    def is_direction(something):
        """Determine if something could be a direction."""
        return (something == Direction.RIGHT) or (something == Direction.LEFT)

    @staticmethod
    def get_name(direction):
        if (direction == Direction.RIGHT):
            return "R"
        elif(direction == Direction.LEFT):
            return "L"

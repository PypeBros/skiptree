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
    def get_opposite(direction):
        """Return the opposite direction."""
        assert Direction.is_direction(direction)
        if(direction == Direction.RIGHT):
            return Direction.LEFT
        else:
            assert direction == Direction.LEFT
            return Direction.RIGHT

    @staticmethod
    def get_name(direction):
        if (direction == Direction.RIGHT):
            return "R"
        elif(direction == Direction.LEFT):
            return "L"
